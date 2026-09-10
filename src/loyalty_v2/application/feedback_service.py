from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError
from loyalty_v2.db.engagement_models import CustomerFeedback, FeedbackSettings
from loyalty_v2.db.models import Customer
from loyalty_v2.db.order_models import Order


class FeedbackError(DomainError):
    code = "FEEDBACK_ERROR"


class FeedbackService:
    async def settings(self, session: AsyncSession, *, organization_id: UUID) -> FeedbackSettings:
        item = await session.scalar(select(FeedbackSettings).where(FeedbackSettings.organization_id == organization_id))
        if item is None:
            item = FeedbackSettings(organization_id=organization_id, positive_from_rating=4, notify_admins_on_rating_at_most=3)
            session.add(item)
            await session.flush()
        return item

    async def submit(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, rating: int, comment: str | None = None, order_id: UUID | None = None) -> CustomerFeedback:
        if rating < 1 or rating > 5:
            raise FeedbackError("Rating must be from 1 to 5")
        customer = await session.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        if customer is None:
            raise FeedbackError("Customer not found")
        if order_id is not None:
            order = await session.scalar(select(Order).where(Order.id == order_id, Order.organization_id == organization_id, Order.customer_id == customer_id))
            if order is None:
                raise FeedbackError("Order does not belong to customer")
        settings = await self.settings(session, organization_id=organization_id)
        item = CustomerFeedback(
            organization_id=organization_id,
            customer_id=customer_id,
            order_id=order_id,
            rating=rating,
            comment=(comment or "").strip() or None,
            status="new",
            routed_to_admins=rating <= settings.notify_admins_on_rating_at_most,
            external_review_offered=rating >= settings.positive_from_rating and bool(settings.external_review_url),
        )
        session.add(item)
        await session.flush()
        return item

    async def resolve(self, session: AsyncSession, *, organization_id: UUID, feedback_id: UUID, staff_id: UUID, resolution_note: str) -> CustomerFeedback:
        item = await session.scalar(select(CustomerFeedback).where(CustomerFeedback.id == feedback_id, CustomerFeedback.organization_id == organization_id).with_for_update())
        if item is None:
            raise FeedbackError("Feedback not found")
        item.status = "resolved"
        item.resolved_at = datetime.now(timezone.utc)
        item.resolved_by_staff_id = staff_id
        item.resolution_note = resolution_note.strip()
        await session.flush()
        return item
