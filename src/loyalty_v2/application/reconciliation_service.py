from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.db.models import PointsAccount, PointsLedgerEntry
from loyalty_v2.db.order_models import Order
from loyalty_v2.db.refund_models import Refund


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    code: str
    object_type: str
    object_id: str
    details: dict


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    organization_id: UUID
    checked_accounts: int
    checked_orders: int
    issues: tuple[ReconciliationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


class ReconciliationService:
    async def run(self, session: AsyncSession, *, organization_id: UUID, limit: int = 10000) -> ReconciliationReport:
        issues: list[ReconciliationIssue] = []
        accounts = (await session.scalars(
            select(PointsAccount)
            .where(PointsAccount.organization_id == organization_id)
            .order_by(PointsAccount.id.asc())
            .limit(limit)
        )).all()
        for account in accounts:
            latest = await session.scalar(
                select(PointsLedgerEntry)
                .where(
                    PointsLedgerEntry.organization_id == organization_id,
                    PointsLedgerEntry.customer_id == account.customer_id,
                    PointsLedgerEntry.account_id == account.id,
                )
                .order_by(PointsLedgerEntry.created_at.desc(), PointsLedgerEntry.id.desc())
                .limit(1)
            )
            if latest is None:
                if account.balance != 0 or account.debt != 0:
                    issues.append(ReconciliationIssue(
                        "ACCOUNT_WITHOUT_LEDGER",
                        "points_account",
                        str(account.id),
                        {"balance": account.balance, "debt": account.debt},
                    ))
                continue
            if latest.balance_after != account.balance or latest.debt_after != account.debt:
                issues.append(ReconciliationIssue(
                    "ACCOUNT_LEDGER_SNAPSHOT_MISMATCH",
                    "points_account",
                    str(account.id),
                    {
                        "account_balance": account.balance,
                        "ledger_balance_after": latest.balance_after,
                        "account_debt": account.debt,
                        "ledger_debt_after": latest.debt_after,
                        "ledger_entry_id": str(latest.id),
                    },
                ))

        orders = (await session.scalars(
            select(Order)
            .where(Order.organization_id == organization_id)
            .order_by(Order.id.asc())
            .limit(limit)
        )).all()
        for order in orders:
            totals = (await session.execute(
                select(
                    func.coalesce(func.sum(Refund.gross_refund_minor), 0),
                    func.coalesce(func.sum(Refund.paid_refund_minor), 0),
                    func.coalesce(func.sum(Refund.restored_points), 0),
                    func.coalesce(func.sum(Refund.qualification_reversal_minor), 0),
                ).where(
                    Refund.organization_id == organization_id,
                    Refund.order_id == order.id,
                )
            )).one()
            gross_refunded, paid_refunded, points_restored, qualification_reversed = (int(x or 0) for x in totals)
            if gross_refunded > order.gross_amount_minor:
                issues.append(ReconciliationIssue("ORDER_OVER_REFUNDED_GROSS", "order", str(order.id), {"order_gross": order.gross_amount_minor, "refunded_gross": gross_refunded}))
            if paid_refunded > order.paid_amount_minor:
                issues.append(ReconciliationIssue("ORDER_OVER_REFUNDED_PAID", "order", str(order.id), {"order_paid": order.paid_amount_minor, "refunded_paid": paid_refunded}))
            if points_restored > order.redeemed_points:
                issues.append(ReconciliationIssue("ORDER_OVER_RESTORED_POINTS", "order", str(order.id), {"redeemed_points": order.redeemed_points, "restored_points": points_restored}))
            if qualification_reversed > order.qualification_amount_minor:
                issues.append(ReconciliationIssue("ORDER_OVER_REVERSED_QUALIFICATION", "order", str(order.id), {"qualification": order.qualification_amount_minor, "reversed": qualification_reversed}))

        return ReconciliationReport(
            organization_id=organization_id,
            checked_accounts=len(accounts),
            checked_orders=len(orders),
            issues=tuple(issues),
        )
