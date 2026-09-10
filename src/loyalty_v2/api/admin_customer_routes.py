from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.admin_customer_service import AdminCustomerService
from loyalty_v2.application.audit_service import AuditService
from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.customer_policy_service import CustomerPolicyService
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2/admin/customers", tags=["admin-customers"])
principals = PrincipalService()
customers = AdminCustomerService()
policies = CustomerPolicyService()
audit = AuditService()


class AdminRequest(BaseModel):
    staff_session_id: UUID


class AdjustPointsRequest(AdminRequest):
    delta: int
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=128)


class BlockRequest(AdminRequest):
    blocked: bool
    reason: str = Field(min_length=1, max_length=500)


class TierOverrideRequest(AdminRequest):
    tier_id: UUID
    reason: str = Field(min_length=1, max_length=500)
    ends_at: datetime | None = None


class RedemptionOverrideRequest(AdminRequest):
    max_percent: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=500)
    ends_at: datetime


async def _admin(session: AsyncSession, staff_session_id: UUID):
    p = await principals.staff(session, staff_session_id=staff_session_id)
    p.require(Permission.ADMIN_ACCESS)
    return p


def _error(exc: DomainError) -> HTTPException:
    if exc.code == "PERMISSION_DENIED": code = status.HTTP_403_FORBIDDEN
    elif exc.code == "STAFF_SESSION_INVALID": code = status.HTTP_401_UNAUTHORIZED
    elif exc.code == "CUSTOMER_NOT_FOUND": code = status.HTTP_404_NOT_FOUND
    else: code = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(code, detail={"code": exc.code, "message": str(exc)})


def _customer_item(x):
    return {"id": x.id, "first_name": x.first_name, "phone": x.phone, "birth_date": x.birth_date, "is_blocked": x.is_blocked, "blocked_at": x.blocked_at, "created_at": x.created_at}


@router.get("")
async def search_customers(staff_session_id: UUID, q: str = Query(default="", max_length=160), limit: int = Query(default=30, ge=1, le=100), session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        return [_customer_item(x) for x in await customers.search(session, organization_id=p.organization_id, query=q, limit=limit)]
    except DomainError as exc: raise _error(exc) from exc


@router.get("/{customer_id}")
async def customer_card(customer_id: UUID, staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        p = await _admin(session, staff_session_id)
        s = await customers.summary(session, organization_id=p.organization_id, customer_id=customer_id)
        tier_override, redemption_override = await customers.active_overrides(session, organization_id=p.organization_id, customer_id=customer_id)
        counters = await customers.category_counters(session, organization_id=p.organization_id, customer_id=customer_id)
        return {
            "customer": _customer_item(s.customer),
            "loyalty": {
                "balance": s.balance,
                "qualification_spend_minor": s.qualification_spend_minor,
                "automatic_tier": {"id": s.automatic_tier.id, "name": s.automatic_tier.name, "cashback_basis_points": s.automatic_tier.cashback_basis_points},
                "effective_tier": {"id": s.effective_tier.id, "name": s.effective_tier.name, "cashback_basis_points": s.effective_tier.cashback_basis_points},
                "redemption_percent": s.redemption_percent,
                "tier_override": None if tier_override is None else {"id": tier_override.id, "tier_id": tier_override.tier_id, "ends_at": tier_override.ends_at, "reason": tier_override.reason},
                "redemption_override": None if redemption_override is None else {"id": redemption_override.id, "max_percent": redemption_override.max_percent, "ends_at": redemption_override.ends_at, "reason": redemption_override.reason},
            },
            "category_counters": [{"category_id": category.id, "code": category.code, "name": category.name, "lifetime_count": counter.lifetime_count, "net_count": counter.net_count} for counter, category in counters],
        }
    except DomainError as exc: raise _error(exc) from exc


@router.get("/{customer_id}/ledger")
async def customer_ledger(customer_id: UUID, staff_session_id: UUID, limit: int = Query(default=100, ge=1, le=500), session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        await customers.summary(session, organization_id=p.organization_id, customer_id=customer_id)
        rows = await customers.ledger(session, organization_id=p.organization_id, customer_id=customer_id, limit=limit)
        return [{"id": x.id, "entry_type": x.entry_type, "delta": x.delta, "balance_after": x.balance_after, "reference_type": x.reference_type, "reference_id": x.reference_id, "reason": x.reason, "created_at": x.created_at} for x in rows]
    except DomainError as exc: raise _error(exc) from exc


@router.get("/{customer_id}/orders")
async def customer_orders(customer_id: UUID, staff_session_id: UUID, limit: int = Query(default=100, ge=1, le=500), session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        await customers.summary(session, organization_id=p.organization_id, customer_id=customer_id)
        rows = await customers.orders(session, organization_id=p.organization_id, customer_id=customer_id, limit=limit)
        return [{"id": x.id, "location_id": x.location_id, "gross_amount_minor": x.gross_amount_minor, "redeemed_points": x.redeemed_points, "paid_amount_minor": x.paid_amount_minor, "points_earned": x.points_earned, "qualification_amount_minor": x.qualification_amount_minor, "category_counts": x.category_counts_snapshot, "status": x.status, "confirmed_at": x.confirmed_at} for x in rows]
    except DomainError as exc: raise _error(exc) from exc


@router.get("/{customer_id}/rewards")
async def customer_rewards(customer_id: UUID, staff_session_id: UUID, limit: int = Query(default=100, ge=1, le=500), session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        await customers.summary(session, organization_id=p.organization_id, customer_id=customer_id)
        rows = await customers.rewards(session, organization_id=p.organization_id, customer_id=customer_id, limit=limit)
        return [{"id": reward.id, "definition_id": definition.id, "name": definition.name, "reward_type": definition.reward_type, "quantity_remaining": reward.quantity_remaining, "status": reward.status, "valid_from": reward.valid_from, "valid_until": reward.valid_until, "source_type": reward.source_type, "issued_at": reward.issued_at, "consumed_at": reward.consumed_at, "revoked_at": reward.revoked_at, "expired_at": reward.expired_at} for reward, definition in rows]
    except DomainError as exc: raise _error(exc) from exc


@router.post("/{customer_id}/points")
async def adjust_points(customer_id: UUID, body: AdjustPointsRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            p.require(Permission.POINTS_ADJUST)
            entry = await customers.adjust_points(session, organization_id=p.organization_id, customer_id=customer_id, actor_staff_id=p.staff_id, delta=body.delta, reason=body.reason, idempotency_key=body.idempotency_key)
        return {"entry_id": entry.id, "delta": entry.delta, "balance_after": entry.balance_after}
    except DomainError as exc: raise _error(exc) from exc


@router.post("/{customer_id}/blocked")
async def set_blocked(customer_id: UUID, body: BlockRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            customer = await customers.set_blocked(session, organization_id=p.organization_id, customer_id=customer_id, actor_staff_id=p.staff_id, blocked=body.blocked, reason=body.reason)
        return {"customer_id": customer.id, "blocked": customer.is_blocked, "blocked_at": customer.blocked_at}
    except DomainError as exc: raise _error(exc) from exc


@router.post("/{customer_id}/tier-override")
async def set_tier_override(customer_id: UUID, body: TierOverrideRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            before, _ = await customers.active_overrides(session, organization_id=p.organization_id, customer_id=customer_id)
            item = await policies.set_tier_override(session, organization_id=p.organization_id, customer_id=customer_id, tier_id=body.tier_id, staff_id=p.staff_id, reason=body.reason, ends_at=body.ends_at)
            await audit.record(session, organization_id=p.organization_id, actor_staff_id=p.staff_id, action="customer.tier_override.set", object_type="customer", object_id=customer_id, before=None if before is None else audit.snapshot(before, ("id", "tier_id", "ends_at", "reason", "is_active")), after=audit.snapshot(item, ("id", "tier_id", "ends_at", "reason", "is_active")))
        return {"id": item.id, "tier_id": item.tier_id, "ends_at": item.ends_at}
    except DomainError as exc: raise _error(exc) from exc


@router.post("/{customer_id}/redemption-override")
async def set_redemption_override(customer_id: UUID, body: RedemptionOverrideRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            _, before = await customers.active_overrides(session, organization_id=p.organization_id, customer_id=customer_id)
            item = await policies.set_redemption_override(session, organization_id=p.organization_id, customer_id=customer_id, max_percent=body.max_percent, staff_id=p.staff_id, reason=body.reason, ends_at=body.ends_at)
            await audit.record(session, organization_id=p.organization_id, actor_staff_id=p.staff_id, action="customer.redemption_override.set", object_type="customer", object_id=customer_id, before=None if before is None else audit.snapshot(before, ("id", "max_percent", "ends_at", "reason", "is_active")), after=audit.snapshot(item, ("id", "max_percent", "ends_at", "reason", "is_active")))
        return {"id": item.id, "max_percent": item.max_percent, "ends_at": item.ends_at}
    except DomainError as exc: raise _error(exc) from exc
