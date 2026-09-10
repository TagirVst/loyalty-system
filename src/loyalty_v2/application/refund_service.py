from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError, PointsService, TierService
from loyalty_v2.db.models import CustomerLoyaltyState, LedgerEntryType
from loyalty_v2.db.order_models import Order
from loyalty_v2.db.refund_models import Refund

CASHIER_CANCEL_WINDOW = timedelta(minutes=10)


class RefundNotAllowed(DomainError):
    code = "REFUND_NOT_ALLOWED"


class RefundAmountInvalid(DomainError):
    code = "REFUND_AMOUNT_INVALID"


@dataclass(frozen=True, slots=True)
class RefundPreview:
    gross_refund_minor: int
    paid_refund_minor: int
    restored_points: int
    reversed_earned_points: int
    qualification_reversal_minor: int
    remaining_gross_minor: int


def proportional(total_effect: int, refund_gross: int, original_gross: int, *, final: bool = False, already: int = 0) -> int:
    if final:
        return max(0, total_effect - already)
    return (total_effect * refund_gross) // original_gross


class RefundService:
    def __init__(self) -> None:
        self.points = PointsService()
        self.tiers = TierService()

    async def _totals(self, session: AsyncSession, order_id: UUID) -> tuple[int, int, int, int, int]:
        rows = await session.execute(
            select(
                func.coalesce(func.sum(Refund.gross_refund_minor), 0),
                func.coalesce(func.sum(Refund.paid_refund_minor), 0),
                func.coalesce(func.sum(Refund.restored_points), 0),
                func.coalesce(func.sum(Refund.reversed_earned_points), 0),
                func.coalesce(func.sum(Refund.qualification_reversal_minor), 0),
            ).where(Refund.order_id == order_id)
        )
        return tuple(int(v) for v in rows.one())  # type: ignore[return-value]

    async def preview(self, session: AsyncSession, *, organization_id: UUID, order_id: UUID, gross_refund_minor: int | None = None) -> RefundPreview:
        order = await session.scalar(select(Order).where(Order.id == order_id, Order.organization_id == organization_id))
        if order is None:
            raise RefundNotAllowed("Order not found")
        refunded_gross, refunded_paid, restored, reversed_earned, reversed_qualification = await self._totals(session, order.id)
        remaining = order.gross_amount_minor - refunded_gross
        requested = remaining if gross_refund_minor is None else gross_refund_minor
        if requested <= 0 or requested > remaining:
            raise RefundAmountInvalid("Refund exceeds remaining refundable amount")
        final = requested == remaining
        return RefundPreview(
            gross_refund_minor=requested,
            paid_refund_minor=proportional(order.paid_amount_minor, requested, order.gross_amount_minor, final=final, already=refunded_paid),
            restored_points=proportional(order.redeemed_points, requested, order.gross_amount_minor, final=final, already=restored),
            reversed_earned_points=proportional(order.points_earned, requested, order.gross_amount_minor, final=final, already=reversed_earned),
            qualification_reversal_minor=proportional(order.qualification_amount_minor, requested, order.gross_amount_minor, final=final, already=reversed_qualification),
            remaining_gross_minor=remaining - requested,
        )

    async def confirm(self, session: AsyncSession, *, organization_id: UUID, order_id: UUID, actor_staff_id: UUID, reason: str, idempotency_key: str, gross_refund_minor: int | None = None, cashier_cancel: bool = False) -> Refund:
        existing = await session.scalar(select(Refund).where(Refund.organization_id == organization_id, Refund.idempotency_key == idempotency_key))
        if existing:
            return existing
        order = await session.scalar(select(Order).where(Order.id == order_id, Order.organization_id == organization_id).with_for_update())
        if order is None:
            raise RefundNotAllowed("Order not found")
        now = datetime.now(timezone.utc)
        if cashier_cancel:
            if gross_refund_minor is not None and gross_refund_minor != order.gross_amount_minor:
                raise RefundNotAllowed("Cashier cancellation must refund the whole remaining order")
            if now - order.confirmed_at > CASHIER_CANCEL_WINDOW:
                raise RefundNotAllowed("Cashier cancellation window has expired")

        preview = await self.preview(session, organization_id=organization_id, order_id=order_id, gross_refund_minor=gross_refund_minor)
        state = await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.customer_id == order.customer_id).with_for_update())
        if state is None:
            raise RefundNotAllowed("Customer loyalty state missing")

        refund = Refund(
            organization_id=organization_id, order_id=order.id, actor_staff_id=actor_staff_id,
            refund_type="full" if preview.remaining_gross_minor == 0 else "partial",
            gross_refund_minor=preview.gross_refund_minor, paid_refund_minor=preview.paid_refund_minor,
            restored_points=preview.restored_points, reversed_earned_points=preview.reversed_earned_points,
            qualification_reversal_minor=preview.qualification_reversal_minor,
            calculation_snapshot={"algorithm": "proportional_floor_final_remainder", "original_gross_minor": order.gross_amount_minor},
            reason=reason, idempotency_key=idempotency_key,
        )
        session.add(refund)
        await session.flush()

        if preview.restored_points:
            await self.points.apply(session, organization_id=organization_id, customer_id=order.customer_id, delta=preview.restored_points, entry_type=LedgerEntryType.REFUND, reference_type="refund", reference_id=refund.id, idempotency_key=f"{idempotency_key}:restore")
        if preview.reversed_earned_points:
            account = await self.points._locked_account(session, organization_id, order.customer_id)
            reversal = min(preview.reversed_earned_points, account.balance)
            if reversal:
                await self.points.apply(session, organization_id=organization_id, customer_id=order.customer_id, delta=-reversal, entry_type=LedgerEntryType.REVERSAL, reference_type="refund", reference_id=refund.id, idempotency_key=f"{idempotency_key}:earned-reversal")
            # Any unrecoverable earned points remain represented by the refund record for reconciliation.

        state.qualification_spend_minor = max(0, state.qualification_spend_minor - preview.qualification_reversal_minor)
        tier_after = await self.tiers.tier_for_spend(session, organization_id, state.qualification_spend_minor)
        state.automatic_tier_id = tier_after.id
        if preview.remaining_gross_minor == 0:
            order.status = "refunded"
        else:
            order.status = "partially_refunded"
        await session.flush()
        return refund
