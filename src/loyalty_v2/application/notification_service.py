from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from string import Formatter
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.segment_service import SegmentService
from loyalty_v2.db.engagement_models import CustomerSegment
from loyalty_v2.db.identity_models import CustomerAuthIdentity
from loyalty_v2.db.models import Customer
from loyalty_v2.db.notification_models import CustomerNotificationPreference, NotificationOutbox
from loyalty_v2.db.notification_template_models import NotificationTemplate


class NotificationProvider(Protocol):
    async def send(self, *, recipient: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class DeliveryBatchResult:
    sent: int = 0
    retried: int = 0
    failed: int = 0
    skipped: int = 0


class NotificationService:
    def __init__(self) -> None: self.segments = SegmentService()

    async def preferences(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID) -> CustomerNotificationPreference:
        item = await session.scalar(select(CustomerNotificationPreference).where(CustomerNotificationPreference.organization_id == organization_id, CustomerNotificationPreference.customer_id == customer_id))
        if item is None:
            item = CustomerNotificationPreference(organization_id=organization_id, customer_id=customer_id, service_enabled=True, marketing_enabled=True); session.add(item); await session.flush()
        return item

    async def set_preferences(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, marketing_enabled: bool) -> CustomerNotificationPreference:
        item = await self.preferences(session, organization_id=organization_id, customer_id=customer_id); item.marketing_enabled = marketing_enabled; return item

    async def render(self, session: AsyncSession, *, organization_id: UUID, code: str, values: dict[str, object], fallback: str) -> str:
        template = await session.scalar(select(NotificationTemplate).where(NotificationTemplate.organization_id == organization_id, NotificationTemplate.code == code, NotificationTemplate.is_active.is_(True)))
        if template is None: return fallback
        required = {name for _, name, _, _ in Formatter().parse(template.body_template) if name}
        if not required.issubset(values): return fallback
        try: return template.body_template.format_map(values)
        except (KeyError, ValueError): return fallback

    async def enqueue(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, body: str, kind: str = "service", template_code: str | None = None, idempotency_key: str | None = None) -> NotificationOutbox | None:
        if kind not in {"service", "marketing"}: raise ValueError("Unsupported notification kind")
        prefs = await self.preferences(session, organization_id=organization_id, customer_id=customer_id)
        if (kind == "service" and not prefs.service_enabled) or (kind == "marketing" and not prefs.marketing_enabled): return None
        if idempotency_key:
            existing = await session.scalar(select(NotificationOutbox).where(NotificationOutbox.organization_id == organization_id, NotificationOutbox.idempotency_key == idempotency_key))
            if existing is not None: return existing
        item = NotificationOutbox(organization_id=organization_id, recipient_type="customer", customer_id=customer_id, recipient_address=None, kind=kind, template_code=template_code, body=body.strip(), status="queued", next_attempt_at=datetime.now(timezone.utc), idempotency_key=idempotency_key); session.add(item); await session.flush(); return item

    async def enqueue_staff_chat(self, session: AsyncSession, *, organization_id: UUID, telegram_chat_id: int, body: str, template_code: str | None = None, idempotency_key: str | None = None) -> NotificationOutbox:
        if idempotency_key:
            existing = await session.scalar(select(NotificationOutbox).where(NotificationOutbox.organization_id == organization_id, NotificationOutbox.idempotency_key == idempotency_key))
            if existing is not None: return existing
        item = NotificationOutbox(organization_id=organization_id, recipient_type="staff_chat", customer_id=None, recipient_address=str(telegram_chat_id), channel="telegram", kind="service", template_code=template_code, body=body.strip(), status="queued", next_attempt_at=datetime.now(timezone.utc), idempotency_key=idempotency_key); session.add(item); await session.flush(); return item

    async def enqueue_segment(self, session: AsyncSession, *, organization_id: UUID, segment_code: str, body: str, campaign_key: str, limit: int = 5000) -> int:
        segment = await session.scalar(select(CustomerSegment).where(CustomerSegment.organization_id == organization_id, CustomerSegment.code == segment_code, CustomerSegment.is_active.is_(True)))
        if segment is None: raise ValueError("Segment not found")
        customer_ids = (await session.scalars(select(Customer.id).where(Customer.organization_id == organization_id, Customer.is_blocked.is_(False)).order_by(Customer.id.asc()).limit(limit))).all(); queued = 0; now = datetime.now(timezone.utc)
        for customer_id in customer_ids:
            if segment_code not in await self.segments.active_codes_for_customer(session, organization_id=organization_id, customer_id=customer_id, now=now): continue
            item = await self.enqueue(session, organization_id=organization_id, customer_id=customer_id, body=body, kind="marketing", template_code="segment_campaign", idempotency_key=f"campaign:{campaign_key}:{customer_id}")
            if item is not None: queued += 1
        return queued

    async def deliver_due(self, session: AsyncSession, *, provider: NotificationProvider, now: datetime | None = None, limit: int = 100) -> DeliveryBatchResult:
        now = now or datetime.now(timezone.utc); rows = (await session.scalars(select(NotificationOutbox).where(NotificationOutbox.status.in_(["queued", "retry"]), NotificationOutbox.next_attempt_at <= now).order_by(NotificationOutbox.created_at.asc()).limit(limit).with_for_update(skip_locked=True))).all(); sent = retried = failed = skipped = 0
        for item in rows:
            if item.recipient_type == "staff_chat": recipient = item.recipient_address
            else:
                identity = await session.scalar(select(CustomerAuthIdentity).where(CustomerAuthIdentity.organization_id == item.organization_id, CustomerAuthIdentity.customer_id == item.customer_id, CustomerAuthIdentity.provider == item.channel, CustomerAuthIdentity.is_active.is_(True), CustomerAuthIdentity.is_verified.is_(True))); recipient = identity.external_subject if identity is not None else None
            if not recipient: item.status="failed"; item.failed_at=now; item.last_error="No active verified delivery identity"; failed += 1; continue
            try: await provider.send(recipient=recipient, body=item.body)
            except Exception as exc:
                item.attempts += 1; item.last_error = str(exc)[:1000]
                if item.attempts >= item.max_attempts: item.status="failed"; item.failed_at=now; failed += 1
                else: item.status="retry"; item.next_attempt_at = now + timedelta(seconds=min(3600, 30 * (2 ** max(0, item.attempts - 1)))); retried += 1
            else: item.attempts += 1; item.status="sent"; item.sent_at=now; item.last_error=None; sent += 1
        return DeliveryBatchResult(sent, retried, failed, skipped)
