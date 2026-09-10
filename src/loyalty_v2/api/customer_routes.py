from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.client_service import ClientService
from loyalty_v2.application.feedback_service import FeedbackService
from loyalty_v2.application.principal import CustomerSessionInvalid, PrincipalService
from loyalty_v2.db.models import Customer
from loyalty_v2.db.order_models import Order
from loyalty_v2.db.reward_models import CustomerReward, RewardDefinition
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2/customer", tags=["customer"])
principals = PrincipalService()
clients = ClientService()
feedback = FeedbackService()


class FeedbackRequest(BaseModel):
    customer_session_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=5000)
    order_id: UUID | None = None


async def _principal(session: AsyncSession, session_id: UUID):
    try:
        return await principals.customer(session, customer_session_id=session_id)
    except CustomerSessionInvalid as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": exc.code, "message": str(exc)}) from exc


@router.get("/me")
async def me(customer_session_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    p = await _principal(session, customer_session_id)
    customer = await session.scalar(select(Customer).where(Customer.id == p.customer_id, Customer.organization_id == p.organization_id))
    state = await clients.home(session, organization_id=p.organization_id, customer_id=p.customer_id)
    return {"id": customer.id, "first_name": customer.first_name, "phone": customer.phone, "birth_date": customer.birth_date, "balance": state.balance, "tier": state.tier_name, "cashback_basis_points": state.cashback_basis_points}


@router.get("/orders")
async def orders(customer_session_id: UUID, limit: int = Query(default=50, ge=1, le=200), session: AsyncSession = Depends(get_session)) -> list[dict]:
    p = await _principal(session, customer_session_id)
    rows = (await session.scalars(select(Order).where(Order.organization_id == p.organization_id, Order.customer_id == p.customer_id).order_by(Order.confirmed_at.desc()).limit(limit))).all()
    return [{"id": x.id, "gross_amount_minor": x.gross_amount_minor, "paid_amount_minor": x.paid_amount_minor, "redeemed_points": x.redeemed_points, "points_earned": x.points_earned, "status": x.status, "confirmed_at": x.confirmed_at} for x in rows]


@router.get("/rewards")
async def rewards(customer_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    p = await _principal(session, customer_session_id)
    rows = (await session.execute(select(CustomerReward, RewardDefinition).join(RewardDefinition, RewardDefinition.id == CustomerReward.reward_definition_id).where(CustomerReward.organization_id == p.organization_id, CustomerReward.customer_id == p.customer_id).order_by(CustomerReward.issued_at.desc()))).all()
    return [{"id": r.id, "name": d.name, "reward_type": d.reward_type, "status": r.status, "quantity_remaining": r.quantity_remaining, "valid_from": r.valid_from, "valid_until": r.valid_until} for r,d in rows]


@router.post("/feedback", status_code=201)
async def submit_feedback(body: FeedbackRequest, session: AsyncSession = Depends(get_session)) -> dict:
    async with session.begin():
        p = await _principal(session, body.customer_session_id)
        item = await feedback.submit(session, organization_id=p.organization_id, customer_id=p.customer_id, rating=body.rating, comment=body.comment, order_id=body.order_id)
        settings = await feedback.settings(session, organization_id=p.organization_id)
    return {"id": item.id, "rating": item.rating, "routed_to_admins": item.routed_to_admins, "external_review_offered": item.external_review_offered, "external_review_url": settings.external_review_url if item.external_review_offered else None}
