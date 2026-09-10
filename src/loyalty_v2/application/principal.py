from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.auth_service import Permission, PermissionDenied, ROLE_PERMISSIONS, StaffSessionInvalid
from loyalty_v2.db.auth_models import StaffSession, StaffTerminal
from loyalty_v2.db.models import Staff


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


class PrincipalService:
    async def staff(self, session: AsyncSession, *, staff_session_id: UUID) -> StaffPrincipal:
        auth_session = await session.scalar(
            select(StaffSession).where(
                StaffSession.id == staff_session_id,
                StaffSession.status == "active",
            )
        )
        if auth_session is None:
            raise StaffSessionInvalid("Staff session is not active")

        staff = await session.scalar(
            select(Staff).where(
                Staff.id == auth_session.staff_id,
                Staff.organization_id == auth_session.organization_id,
                Staff.is_active.is_(True),
            )
        )
        terminal = await session.scalar(
            select(StaffTerminal).where(
                StaffTerminal.id == auth_session.terminal_id,
                StaffTerminal.organization_id == auth_session.organization_id,
                StaffTerminal.is_active.is_(True),
            )
        )
        if staff is None or terminal is None:
            raise StaffSessionInvalid("Staff session references inactive staff or terminal")
        if staff.location_id != terminal.location_id:
            raise StaffSessionInvalid("Staff and terminal locations do not match")

        return StaffPrincipal(
            session_id=auth_session.id,
            organization_id=auth_session.organization_id,
            location_id=terminal.location_id,
            terminal_id=terminal.id,
            staff_id=staff.id,
            permissions=ROLE_PERMISSIONS.get(staff.role, frozenset()),
        )
