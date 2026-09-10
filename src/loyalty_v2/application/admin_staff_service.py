from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.audit_service import AuditService
from loyalty_v2.application.auth_service import StaffAuthService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.auth_models import StaffSession, StaffTerminal
from loyalty_v2.db.models import Location, Staff, StaffRole


class StaffConfigNotFound(DomainError):
    code = "STAFF_CONFIG_NOT_FOUND"


class StaffConfigInvalid(DomainError):
    code = "STAFF_CONFIG_INVALID"


class AdminStaffService:
    def __init__(self) -> None:
        self.auth = StaffAuthService()
        self.audit = AuditService()

    async def _location(self, session: AsyncSession, organization_id: UUID, location_id: UUID) -> Location:
        item = await session.scalar(select(Location).where(
            Location.id == location_id,
            Location.organization_id == organization_id,
            Location.is_active.is_(True),
        ))
        if item is None:
            raise StaffConfigInvalid("Location is unavailable")
        return item

    @staticmethod
    def _role(role: str) -> str:
        value = role.strip().lower()
        if value not in {StaffRole.BARISTA.value, StaffRole.ADMIN.value}:
            raise StaffConfigInvalid("Unsupported staff role")
        return value

    @staticmethod
    def _staff_snapshot(item: Staff) -> dict:
        return {
            "id": item.id,
            "location_id": item.location_id,
            "name": item.name,
            "role": item.role,
            "is_active": item.is_active,
            "pin_configured": bool(item.pin_hash and item.pin_fingerprint),
        }

    @staticmethod
    def _terminal_snapshot(item: StaffTerminal) -> dict:
        return {
            "id": item.id,
            "location_id": item.location_id,
            "telegram_chat_id": item.telegram_chat_id,
            "name": item.name,
            "is_active": item.is_active,
        }

    async def list_staff(self, session: AsyncSession, organization_id: UUID) -> list[Staff]:
        return list((await session.scalars(select(Staff).where(
            Staff.organization_id == organization_id
        ).order_by(Staff.name.asc(), Staff.id.asc()))).all())

    async def create_staff(self, session: AsyncSession, *, organization_id: UUID, actor_staff_id: UUID,
                           location_id: UUID, name: str, role: str, pin: str, is_active: bool = True) -> Staff:
        await self._location(session, organization_id, location_id)
        role = self._role(role)
        name = name.strip()
        if not name:
            raise StaffConfigInvalid("Staff name is required")
        self.auth.validate_pin_format(pin)
        item = Staff(
            organization_id=organization_id,
            location_id=location_id,
            name=name,
            role=role,
            pin_hash=self.auth.hash_pin(pin),
            pin_fingerprint=self.auth.fingerprint(organization_id, pin),
            is_active=is_active,
        )
        session.add(item)
        await session.flush()
        await self.audit.record(session, organization_id=organization_id, actor_staff_id=actor_staff_id,
                                action="staff.create", object_type="staff", object_id=item.id,
                                after=self._staff_snapshot(item))
        return item

    async def update_staff(self, session: AsyncSession, *, organization_id: UUID, actor_staff_id: UUID,
                           staff_id: UUID, name: str | None = None, role: str | None = None,
                           location_id: UUID | None = None, is_active: bool | None = None) -> Staff:
        item = await session.scalar(select(Staff).where(
            Staff.id == staff_id, Staff.organization_id == organization_id
        ).with_for_update())
        if item is None:
            raise StaffConfigNotFound("Staff member not found")
        before = self._staff_snapshot(item)
        if location_id is not None:
            await self._location(session, organization_id, location_id)
            item.location_id = location_id
        if name is not None:
            name = name.strip()
            if not name:
                raise StaffConfigInvalid("Staff name is required")
            item.name = name
        if role is not None:
            item.role = self._role(role)
        if is_active is not None:
            item.is_active = is_active
            if not is_active:
                sessions = (await session.scalars(select(StaffSession).where(
                    StaffSession.staff_id == item.id, StaffSession.status == "active"
                ).with_for_update())).all()
                for auth_session in sessions:
                    auth_session.status = "ended"
        await session.flush()
        await self.audit.record(session, organization_id=organization_id, actor_staff_id=actor_staff_id,
                                action="staff.update", object_type="staff", object_id=item.id,
                                before=before, after=self._staff_snapshot(item))
        return item

    async def set_pin(self, session: AsyncSession, *, organization_id: UUID, actor_staff_id: UUID,
                      staff_id: UUID, pin: str) -> Staff:
        item = await session.scalar(select(Staff).where(
            Staff.id == staff_id, Staff.organization_id == organization_id
        ).with_for_update())
        if item is None:
            raise StaffConfigNotFound("Staff member not found")
        self.auth.validate_pin_format(pin)
        item.pin_hash = self.auth.hash_pin(pin)
        item.pin_fingerprint = self.auth.fingerprint(organization_id, pin)
        active_sessions = (await session.scalars(select(StaffSession).where(
            StaffSession.staff_id == item.id, StaffSession.status == "active"
        ).with_for_update())).all()
        for auth_session in active_sessions:
            auth_session.status = "ended"
        await session.flush()
        await self.audit.record(session, organization_id=organization_id, actor_staff_id=actor_staff_id,
                                action="staff.pin_changed", object_type="staff", object_id=item.id,
                                metadata={"sessions_ended": len(active_sessions)})
        return item

    async def list_terminals(self, session: AsyncSession, organization_id: UUID) -> list[StaffTerminal]:
        return list((await session.scalars(select(StaffTerminal).where(
            StaffTerminal.organization_id == organization_id
        ).order_by(StaffTerminal.name.asc(), StaffTerminal.id.asc()))).all())

    async def create_terminal(self, session: AsyncSession, *, organization_id: UUID, actor_staff_id: UUID,
                              location_id: UUID, telegram_chat_id: int, name: str,
                              is_active: bool = True) -> StaffTerminal:
        await self._location(session, organization_id, location_id)
        name = name.strip()
        if not name:
            raise StaffConfigInvalid("Terminal name is required")
        item = StaffTerminal(organization_id=organization_id, location_id=location_id,
                             telegram_chat_id=telegram_chat_id, name=name, is_active=is_active)
        session.add(item)
        await session.flush()
        await self.audit.record(session, organization_id=organization_id, actor_staff_id=actor_staff_id,
                                action="terminal.create", object_type="staff_terminal", object_id=item.id,
                                after=self._terminal_snapshot(item))
        return item

    async def update_terminal(self, session: AsyncSession, *, organization_id: UUID, actor_staff_id: UUID,
                              terminal_id: UUID, name: str | None = None, location_id: UUID | None = None,
                              telegram_chat_id: int | None = None, is_active: bool | None = None) -> StaffTerminal:
        item = await session.scalar(select(StaffTerminal).where(
            StaffTerminal.id == terminal_id, StaffTerminal.organization_id == organization_id
        ).with_for_update())
        if item is None:
            raise StaffConfigNotFound("Terminal not found")
        before = self._terminal_snapshot(item)
        if location_id is not None:
            await self._location(session, organization_id, location_id)
            item.location_id = location_id
        if name is not None:
            name = name.strip()
            if not name:
                raise StaffConfigInvalid("Terminal name is required")
            item.name = name
        if telegram_chat_id is not None:
            item.telegram_chat_id = telegram_chat_id
        if is_active is not None:
            item.is_active = is_active
        if is_active is False or location_id is not None:
            sessions = (await session.scalars(select(StaffSession).where(
                StaffSession.terminal_id == item.id, StaffSession.status == "active"
            ).with_for_update())).all()
            for auth_session in sessions:
                auth_session.status = "ended"
        await session.flush()
        await self.audit.record(session, organization_id=organization_id, actor_staff_id=actor_staff_id,
                                action="terminal.update", object_type="staff_terminal", object_id=item.id,
                                before=before, after=self._terminal_snapshot(item))
        return item
