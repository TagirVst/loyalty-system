from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import CustomerNotFound
from loyalty_v2.db.customer_auth_models import CustomerSession
from loyalty_v2.db.identity_models import CustomerAuthIdentity
from loyalty_v2.db.models import Customer


class CustomerAuthService:
    async def open_session(self, session: AsyncSession, *, organization_id: UUID, provider: str, external_subject: str, external_session_key: str, ttl: timedelta | None = timedelta(days=30)) -> CustomerSession:
        provider = provider.strip().lower()
        identity = await session.scalar(select(CustomerAuthIdentity).where(CustomerAuthIdentity.organization_id == organization_id, CustomerAuthIdentity.provider == provider, CustomerAuthIdentity.external_subject == external_subject, CustomerAuthIdentity.is_active.is_(True), CustomerAuthIdentity.is_verified.is_(True)))
        if identity is None:
            raise CustomerNotFound("Customer identity not found")
        customer = await session.scalar(select(Customer).where(Customer.id == identity.customer_id, Customer.organization_id == organization_id, Customer.is_blocked.is_(False)))
        if customer is None:
            raise CustomerNotFound("Customer not available")
        now = datetime.now(timezone.utc)
        existing = await session.scalar(select(CustomerSession).where(CustomerSession.organization_id == organization_id, CustomerSession.provider == provider, CustomerSession.external_session_key == external_session_key).with_for_update())
        if existing is not None:
            existing.customer_id = customer.id
            existing.identity_id = identity.id
            existing.status = "active"
            existing.last_seen_at = now
            existing.expires_at = now + ttl if ttl is not None else None
            existing.ended_at = None
            return existing
        item = CustomerSession(organization_id=organization_id, customer_id=customer.id, identity_id=identity.id, provider=provider, external_session_key=external_session_key, status="active", last_seen_at=now, expires_at=now + ttl if ttl is not None else None)
        session.add(item)
        await session.flush()
        return item

    async def end_session(self, session: AsyncSession, *, customer_session_id: UUID) -> None:
        item = await session.scalar(select(CustomerSession).where(CustomerSession.id == customer_session_id).with_for_update())
        if item is None:
            return
        item.status = "ended"
        item.ended_at = datetime.now(timezone.utc)
