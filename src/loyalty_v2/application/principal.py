from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.auth_service import Permission, PermissionDenied, ROLE_PERMISSIONS, StaffSessionInvalid
from loyalty_v2.db.auth_models import StaffSession, StaffTerminal
from loyalty_v2.db.customer_auth_models import CustomerSession
from loyalty_v2.db.identity_models import CustomerAuthIdentity
from loyalty_v2.db.models import Customer, Staff


@dataclass(frozen=True, slots=True)
class StaffPrincipal:
    session_id: UUID
    organization_id: UUID
    location_id: UUID
    terminal_id: UUID
    staff_id: UUID
    permissions: frozenset[Permission]

    def require(self, permission: Permission) -> None:
        if permission not in self.permissions:
            raise PermissionDenied(f"Permission {permission.value} is required")


@dataclass(frozen=True, slots=True)
class CustomerPrincipal:
    session_id: UUID
    organization_id: UUID
    customer_id: UUID
    identity_id: UUID
    provider: str


class CustomerSessionInvalid(StaffSessionInvalid):
    code = "CUSTOMER_SESSION_INVALID"


class PrincipalService:
    async def staff(self, session: AsyncSession, *, staff_session_id: UUID) -> StaffPrincipal:
        auth_session = await session.scalar(select(StaffSession).where(StaffSession.id == staff_session_id, StaffSession.status == "active"))
        if auth_session is None:
            raise StaffSessionInvalid("Staff session is not active")
        staff = await session.scalar(select(Staff).where(Staff.id == auth_session.staff_id, Staff.organization_id == auth_session.organization_id, Staff.is_active.is_(True)))
        terminal = await session.scalar(select(StaffTerminal).where(StaffTerminal.id == auth_session.terminal_id, StaffTerminal.organization_id == auth_session.organization_id, StaffTerminal.is_active.is_(True)))
        if staff is None or terminal is None:
            raise StaffSessionInvalid("Staff session references inactive staff or terminal")
        if staff.location_id != terminal.location_id:
            raise StaffSessionInvalid("Staff and terminal locations do not match")
        return StaffPrincipal(auth_session.id, auth_session.organization_id, terminal.location_id, terminal.id, staff.id, ROLE_PERMISSIONS.get(staff.role, frozenset()))

    async def customer(self, session: AsyncSession, *, customer_session_id: UUID) -> CustomerPrincipal:
        now = datetime.now(timezone.utc)
        auth_session = await session.scalar(select(CustomerSession).where(CustomerSession.id == customer_session_id, CustomerSession.status == "active"))
        if auth_session is None or (auth_session.expires_at is not None and auth_session.expires_at <= now):
            raise CustomerSessionInvalid("Customer session is not active")
        identity = await session.scalar(select(CustomerAuthIdentity).where(CustomerAuthIdentity.id == auth_session.identity_id, CustomerAuthIdentity.organization_id == auth_session.organization_id, CustomerAuthIdentity.customer_id == auth_session.customer_id, CustomerAuthIdentity.is_active.is_(True), CustomerAuthIdentity.is_verified.is_(True)))
        customer = await session.scalar(select(Customer).where(Customer.id == auth_session.customer_id, Customer.organization_id == auth_session.organization_id, Customer.is_blocked.is_(False)))
        if identity is None or customer is None:
            raise CustomerSessionInvalid("Customer session references unavailable customer or identity")
        auth_session.last_seen_at = now
        return CustomerPrincipal(auth_session.id, auth_session.organization_id, auth_session.customer_id, identity.id, identity.provider)
