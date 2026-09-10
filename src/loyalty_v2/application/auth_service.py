from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError
from loyalty_v2.core.config import get_settings
from loyalty_v2.db.auth_models import StaffPinThrottle, StaffSession, StaffTerminal
from loyalty_v2.db.models import Staff, StaffRole


class Permission(StrEnum):
    SALE_CREATE = "sale:create"
    SALE_CONFIRM = "sale:confirm"
    SALE_CANCEL_OWN = "sale:cancel_own"
    REWARD_REDEEM = "reward:redeem"
    ADMIN_ACCESS = "admin:access"
    POINTS_ADJUST = "points:adjust"
    STAFF_MANAGE = "staff:manage"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    StaffRole.BARISTA.value: frozenset({Permission.SALE_CREATE, Permission.SALE_CONFIRM, Permission.SALE_CANCEL_OWN, Permission.REWARD_REDEEM}),
    StaffRole.ADMIN.value: frozenset(Permission),
}


class InvalidPin(DomainError): code = "INVALID_PIN"
class PinLocked(DomainError): code = "PIN_LOCKED"
class TerminalNotAuthorized(DomainError): code = "TERMINAL_NOT_AUTHORIZED"
class StaffSessionInvalid(DomainError): code = "STAFF_SESSION_INVALID"
class PermissionDenied(DomainError): code = "PERMISSION_DENIED"


@dataclass(frozen=True, slots=True)
class AuthAttempt:
    auth_session: StaffSession | None = None
    error: DomainError | None = None


class StaffAuthService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.hasher = PasswordHasher()

    def validate_pin_format(self, pin: str) -> None:
        if len(pin) != 6 or not pin.isdigit():
            raise InvalidPin("PIN must contain exactly 6 digits")

    def hash_pin(self, pin: str) -> str:
        self.validate_pin_format(pin)
        return self.hasher.hash(pin)

    def fingerprint(self, organization_id: UUID, pin: str) -> str:
        self.validate_pin_format(pin)
        return hmac.new(self.settings.pin_fingerprint_secret.encode(), f"{organization_id}:{pin}".encode(), hashlib.sha256).hexdigest()

    async def authenticate_attempt(self, session: AsyncSession, *, organization_id: UUID, terminal_id: UUID, pin: str) -> AuthAttempt:
        try:
            self.validate_pin_format(pin)
        except DomainError as exc:
            return AuthAttempt(error=exc)
        now = datetime.now(timezone.utc)
        terminal = await session.scalar(select(StaffTerminal).where(StaffTerminal.id == terminal_id, StaffTerminal.organization_id == organization_id, StaffTerminal.is_active.is_(True)))
        if terminal is None:
            return AuthAttempt(error=TerminalNotAuthorized("Staff terminal is not authorized"))
        throttle = await session.scalar(select(StaffPinThrottle).where(StaffPinThrottle.organization_id == organization_id, StaffPinThrottle.terminal_id == terminal_id).with_for_update())
        if throttle is None:
            throttle = StaffPinThrottle(organization_id=organization_id, terminal_id=terminal_id)
            session.add(throttle)
            await session.flush()
        if throttle.locked_until and throttle.locked_until > now:
            return AuthAttempt(error=PinLocked(f"PIN entry locked until {throttle.locked_until.isoformat()}"))
        fp = self.fingerprint(organization_id, pin)
        staff = await session.scalar(select(Staff).where(Staff.organization_id == organization_id, Staff.pin_fingerprint == fp, Staff.is_active.is_(True)))
        verified = False
        if staff and staff.pin_hash:
            try:
                verified = self.hasher.verify(staff.pin_hash, pin)
            except VerifyMismatchError:
                verified = False
        if not verified or staff is None:
            throttle.failed_attempts += 1
            if throttle.failed_attempts >= self.settings.pin_failures_before_lock:
                throttle.lock_level += 1
                throttle.locked_until = now + timedelta(seconds=self.settings.pin_base_lock_seconds * (2 ** (throttle.lock_level - 1)))
                throttle.failed_attempts = 0
            await session.flush()
            return AuthAttempt(error=InvalidPin("Invalid staff PIN"))
        if staff.location_id != terminal.location_id:
            return AuthAttempt(error=PermissionDenied("Staff member is assigned to another location"))
        throttle.failed_attempts = 0
        throttle.locked_until = None
        # A successful login starts a new risk epoch; old failures no longer increase future lock duration forever.
        throttle.lock_level = 0
        existing = await session.scalar(select(StaffSession).where(StaffSession.terminal_id == terminal_id, StaffSession.status == "active").with_for_update())
        if existing:
            existing.status = "ended"
            existing.ended_at = now
        auth_session = StaffSession(organization_id=organization_id, terminal_id=terminal_id, staff_id=staff.id, status="active", authenticated_at=now, last_seen_at=now)
        session.add(auth_session)
        await session.flush()
        return AuthAttempt(auth_session=auth_session)

    async def authenticate(self, session: AsyncSession, *, organization_id: UUID, terminal_id: UUID, pin: str) -> StaffSession:
        """Compatibility API. Prefer authenticate_attempt when caller owns transaction boundaries."""
        attempt = await self.authenticate_attempt(session, organization_id=organization_id, terminal_id=terminal_id, pin=pin)
        if attempt.error:
            raise attempt.error
        assert attempt.auth_session is not None
        return attempt.auth_session

    async def require(self, session: AsyncSession, *, staff_session_id: UUID, permission: Permission) -> tuple[StaffSession, Staff]:
        auth_session = await session.scalar(select(StaffSession).where(StaffSession.id == staff_session_id, StaffSession.status == "active"))
        if auth_session is None:
            raise StaffSessionInvalid("Staff session is not active")
        staff = await session.scalar(select(Staff).where(Staff.id == auth_session.staff_id, Staff.organization_id == auth_session.organization_id, Staff.is_active.is_(True)))
        if staff is None:
            raise StaffSessionInvalid("Staff member is inactive")
        role = staff.role.value if isinstance(staff.role, StaffRole) else staff.role
        if permission not in ROLE_PERMISSIONS.get(role, frozenset()):
            raise PermissionDenied(f"Permission {permission.value} is required")
        auth_session.last_seen_at = datetime.now(timezone.utc)
        return auth_session, staff

    async def logout(self, session: AsyncSession, staff_session_id: UUID) -> None:
        auth_session = await session.scalar(select(StaffSession).where(StaffSession.id == staff_session_id).with_for_update())
        if auth_session is None or auth_session.status != "active":
            raise StaffSessionInvalid("Staff session is not active")
        auth_session.status = "ended"
        auth_session.ended_at = datetime.now(timezone.utc)
