from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.notification_service import NotificationService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.auth_models import StaffSession, StaffTerminal
from loyalty_v2.db.engagement_models import CustomerFeedback, FeedbackSettings
from loyalty_v2.db.models import Customer, Staff
from loyalty_v2.db.order_models import Order


class FeedbackError(DomainError):
    code = "FEEDBACK_ERROR"


class FeedbackService:
    def __init__(self) -> None:
        self.notifications = NotificationService()

    async def settings(self, session: AsyncSession, *, organization_id: UUID) -> FeedbackSettings:
        item = await session.scalar(select(FeedbackSettings).where(FeedbackSettings.organization_id == organization_id))
        if item is None:
            item = FeedbackSettings(organization_id=organization_id, positive_from_rating=4, notify_admins_on_rating_at_most=3)
            session.add(item); await session.flush()
        return item

    async def submit(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, rating: int, comment: str | None = None, order_id: UUID | None = None) -> CustomerFeedback:
        if rating < 1 or rating > 5: raise FeedbackError("Rating must be from 1 to 5")
        customer = await session.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        if customer is None: raise FeedbackError("Customer not found")
        if order_id is not None:
            order = await session.scalar(select(Order).where(Order.id == order_id, Order.organization_id == organization_id, Order.customer_id == customer_id))
            if order is None: raise FeedbackError("Order does not belong to customer")
        settings = await self.settings(session, organization_id=organization_id)
        item = CustomerFeedback(organization_id=organization_id, customer_id=customer_id, order_id=order_id, rating=rating, comment=(comment or "").strip() or None, status="new", routed_to_admins=rating <= settings.notify_admins_on_rating_at_most, external_review_offered=rating >= settings.positive_from_rating and bool(settings.external_review_url))
        session.add(item); await session.flush()
        if item.routed_to_admins:
            chat_ids = (await session.scalars(select(StaffTerminal.telegram_chat_id).join(StaffSession, StaffSession.terminal_id == StaffTerminal.id).join(Staff, Staff.id == StaffSession.staff_id).where(StaffTerminal.organization_id == organization_id, StaffTerminal.is_active.is_(True), StaffSession.status == "active", Staff.is_active.is_(True), Staff.role == "admin").distinct())).all()
            preview = item.comment or "Без комментария"
            text = f"Новый отзыв: {rating}/5\nКлиент: {customer.first_name}\n{preview[:700]}"
            for chat_id in chat_ids:
                await self.notifications.enqueue_staff_chat(session, organization_id=organization_id, telegram_chat_id=chat_id, body=text, template_code="negative_feedback", idempotency_key=f"feedback:{item.id}:chat:{chat_id}")
        return item

    async def resolve(self, session: AsyncSession, *, organization_id: UUID, feedback_id: UUID, staff_id: UUID, resolution_note: str) -> CustomerFeedback:
        item = await session.scalar(select(CustomerFeedback).where(CustomerFeedback.id == feedback_id, CustomerFeedback.organization_id == organization_id).with_for_update())
        if item is None: raise FeedbackError("Feedback not found")
        item.status = "resolved"; item.resolved_at = datetime.now(timezone.utc); item.resolved_by_staff_id = staff_id; item.resolution_note = resolution_note.strip()
        await session.flush(); return item
