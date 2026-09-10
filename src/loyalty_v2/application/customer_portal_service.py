from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.client_service import ClientService
from loyalty_v2.application.feedback_service import FeedbackService
from loyalty_v2.application.order_service import IdentificationService
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.db.models import PointsLedgerEntry
from loyalty_v2.db.order_models import Order
from loyalty_v2.db.reward_models import CustomerReward, RewardDefinition


class CustomerPortalService:
    def __init__(self) -> None:
        self.principals = PrincipalService()
        self.client = ClientService()
        self.identification = IdentificationService()
        self.feedback_service = FeedbackService()

    async def home(self, session: AsyncSession, *, customer_session_id: UUID):
        p = await self.principals.customer(session, customer_session_id=customer_session_id)
        return await self.client.home(session, organization_id=p.organization_id, customer_id=p.customer_id)

    async def identification_code(self, session: AsyncSession, *, customer_session_id: UUID):
        p = await self.principals.customer(session, customer_session_id=customer_session_id)
        return await self.identification.generate(session, organization_id=p.organization_id, customer_id=p.customer_id)

    async def rewards(self, session: AsyncSession, *, customer_session_id: UUID):
        p = await self.principals.customer(session, customer_session_id=customer_session_id)
        rows = await session.execute(
            select(CustomerReward, RewardDefinition)
            .join(RewardDefinition, RewardDefinition.id == CustomerReward.reward_definition_id)
            .where(
                CustomerReward.organization_id == p.organization_id,
                CustomerReward.customer_id == p.customer_id,
                CustomerReward.status.in_(["issued", "active"]),
                CustomerReward.quantity_remaining > 0,
            )
            .order_by(CustomerReward.issued_at.desc())
        )
        return rows.all()

    async def history(self, session: AsyncSession, *, customer_session_id: UUID, limit: int = 20) -> list[PointsLedgerEntry]:
        p = await self.principals.customer(session, customer_session_id=customer_session_id)
        return list((await session.scalars(
            select(PointsLedgerEntry)
            .where(
                PointsLedgerEntry.organization_id == p.organization_id,
                PointsLedgerEntry.customer_id == p.customer_id,
            )
            .order_by(PointsLedgerEntry.created_at.desc(), PointsLedgerEntry.id.desc())
            .limit(limit)
        )).all())

    async def orders(self, session: AsyncSession, *, customer_session_id: UUID, limit: int = 20) -> list[Order]:
        p = await self.principals.customer(session, customer_session_id=customer_session_id)
        return list((await session.scalars(
            select(Order)
            .where(Order.organization_id == p.organization_id, Order.customer_id == p.customer_id)
            .order_by(Order.confirmed_at.desc(), Order.id.desc())
            .limit(limit)
        )).all())

    async def submit_feedback(self, session: AsyncSession, *, customer_session_id: UUID, rating: int, comment: str | None = None, order_id: UUID | None = None):
        p = await self.principals.customer(session, customer_session_id=customer_session_id)
        return await self.feedback_service.submit(
            session,
            organization_id=p.organization_id,
            customer_id=p.customer_id,
            rating=rating,
            comment=comment,
            order_id=order_id,
        )
