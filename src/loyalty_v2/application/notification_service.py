from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.db.identity_models import CustomerAuthIdentity
from loyalty_v2.db.notification_models import CustomerNotificationPreference, NotificationOutbox


class NotificationDeliveryError(Exception): pass


class NotificationProvider(Protocol):
    async def send(self, *, recipient: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class DeliveryBatchResult:
    sent: int = 0
    retried: int = 0
    failed: int = 0
    skipped: int = 0


class NotificationService:
    async def preferences(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID) -> CustomerNotificationPreference:
        item = await session.scalar(select(CustomerNotificationPreference).where(CustomerNotificationPreference.organization_id == organization_id, CustomerNotificationPreference.customer_id == customer_id))
        if item is None:
            item = CustomerNotificationPreference(organization_id=organization_id, customer_id=customer_id, service_enabled=True, marketing_enabled=True)
            session.add(item); await session.flush()
        return item

    async def set_preferences(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, marketing_enabled: bool) -> CustomerNotificationPreference:
        item = await self.preferences(session, organization_id=organization_id, customer_id=customer_id)
        item.marketing_enabled = marketing_enabled
        return item

    async def enqueue(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, body: str, kind: str = "service", template_code: str | None = None, idempotency_key: str | None = None) -> NotificationOutbox | None:
        if kind not in {"service", "marketing"}: raise ValueError("Unsupported notification kind")
        prefs = await self.preferences(session, organization_id=organization_id, customer_id=customer_id)
        if (kind == "service" and not prefs.service_enabled) or (kind == "marketing" and not prefs.marketing_enabled): return None
        if idempotency_key:
            existing = await session.scalar(select(NotificationOutbox).where(NotificationOutbox.organization_id == organization_id, NotificationOutbox.idempotency_key == idempotency_key))
            if existing is not None: return existing
        item = NotificationOutbox(organization_id=organization_id, customer_id=customer_id, kind=kind, template_code=template_code, body=body.strip(), status="queued", next_attempt_at=datetime.now(timezone.utc), idempotency_key=idempotency_key)
        session.add(item); await session.flush(); return item

    async def deliver_due(self, session: AsyncSession, *, provider: NotificationProvider, now: datetime | None = None, limit: int = 100) -> DeliveryBatchResult:
        now = now or datetime.now(timezone.utc)
        rows = (await session.scalars(select(NotificationOutbox).where(NotificationOutbox.status.in_(["queued", "retry"]), NotificationOutbox.next_attempt_at <= now).order_by(NotificationOutbox.created_at.asc()).limit(limit).with_for_update(skip_locked=True))).all()
        sent = retried = failed = skipped = 0
        for item in rows:
            identity = await session.scalar(select(CustomerAuthIdentity).where(CustomerAuthIdentity.organization_id == item.organization_id, CustomerAuthIdentity.customer_id == item.customer_id, CustomerAuthIdentity.provider == item.channel, CustomerAuthIdentity.is_active.is_(True), CustomerAuthIdentity.is_verified.is_(True)))
            if identity is None:
                item.status="failed"; item.failed_at=now; item.last_error="No active verified delivery identity"; failed += 1; continue
            try:
                await provider.send(recipient=identity.external_subject, body=item.body)
            except Exception as exc:
                item.attempts += 1; item.last_error = str(exc)[:1000]
                if item.attempts >= item.max_attempts:
                    item.status="failed"; item.failed_at=now; failed += 1
                else:
                    item.status="retry"; item.next_attempt_at = now + timedelta(seconds=min(3600, 30 * (2 ** max(0, item.attempts - 1)))); retried += 1
            else:
                item.attempts += 1; item.status="sent"; item.sent_at=now; item.last_error=None; sent += 1
        return DeliveryBatchResult(sent, retried, failed, skipped)
