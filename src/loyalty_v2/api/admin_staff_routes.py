from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.admin_staff_service import AdminStaffService
from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2/admin/staff", tags=["admin-staff"])
principals = PrincipalService()
service = AdminStaffService()


class AdminRequest(BaseModel):
    staff_session_id: UUID


class CreateStaffRequest(AdminRequest):
    location_id: UUID
    name: str = Field(min_length=1, max_length=160)
    role: str = Field(pattern=r"^(barista|admin)$")
    pin: str = Field(pattern=r"^\d{6}$")
    is_active: bool = True


class UpdateStaffRequest(AdminRequest):
    location_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = Field(default=None, pattern=r"^(barista|admin)$")
    is_active: bool | None = None


class ChangePinRequest(AdminRequest):
    pin: str = Field(pattern=r"^\d{6}$")


class CreateTerminalRequest(AdminRequest):
    location_id: UUID
    telegram_chat_id: int
    name: str = Field(min_length=1, max_length=160)
    is_active: bool = True


class UpdateTerminalRequest(AdminRequest):
    location_id: UUID | None = None
    telegram_chat_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    is_active: bool | None = None


async def _admin(session: AsyncSession, staff_session_id: UUID):
    principal = await principals.staff(session, staff_session_id=staff_session_id)
    principal.require(Permission.STAFF_MANAGE)
    return principal


def _error(exc: DomainError) -> HTTPException:
    if exc.code == "STAFF_SESSION_INVALID": code = status.HTTP_401_UNAUTHORIZED
    elif exc.code == "PERMISSION_DENIED": code = status.HTTP_403_FORBIDDEN
    elif exc.code == "STAFF_CONFIG_NOT_FOUND": code = status.HTTP_404_NOT_FOUND
    else: code = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(code, detail={"code": exc.code, "message": str(exc)})


def _conflict(exc: IntegrityError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail={"code": "STAFF_CONFIG_CONFLICT", "message": "PIN, Telegram chat, or relation already exists"})


def _staff(x):
    return {"id": x.id, "location_id": x.location_id, "name": x.name, "role": x.role,
            "is_active": x.is_active, "pin_configured": bool(x.pin_hash and x.pin_fingerprint)}


def _terminal(x):
    return {"id": x.id, "location_id": x.location_id, "telegram_chat_id": x.telegram_chat_id,
            "name": x.name, "is_active": x.is_active}


@router.get("")
async def list_staff(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        return [_staff(x) for x in await service.list_staff(session, p.organization_id)]
    except DomainError as exc:
        raise _error(exc) from exc


@router.post("", status_code=201)
async def create_staff(body: CreateStaffRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await service.create_staff(session, organization_id=p.organization_id, actor_staff_id=p.staff_id,
                                              location_id=body.location_id, name=body.name, role=body.role,
                                              pin=body.pin, is_active=body.is_active)
        return _staff(item)
    except DomainError as exc:
        raise _error(exc) from exc
    except IntegrityError as exc:
        raise _conflict(exc) from exc


@router.patch("/{staff_id}")
async def update_staff(staff_id: UUID, body: UpdateStaffRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await service.update_staff(session, organization_id=p.organization_id, actor_staff_id=p.staff_id,
                                              staff_id=staff_id, location_id=body.location_id, name=body.name,
                                              role=body.role, is_active=body.is_active)
        return _staff(item)
    except DomainError as exc:
        raise _error(exc) from exc


@router.post("/{staff_id}/pin")
async def change_pin(staff_id: UUID, body: ChangePinRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await service.set_pin(session, organization_id=p.organization_id, actor_staff_id=p.staff_id,
                                         staff_id=staff_id, pin=body.pin)
        return _staff(item)
    except DomainError as exc:
        raise _error(exc) from exc
    except IntegrityError as exc:
        raise _conflict(exc) from exc


@router.get("/terminals/list")
async def list_terminals(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        return [_terminal(x) for x in await service.list_terminals(session, p.organization_id)]
    except DomainError as exc:
        raise _error(exc) from exc


@router.post("/terminals", status_code=201)
async def create_terminal(body: CreateTerminalRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await service.create_terminal(session, organization_id=p.organization_id, actor_staff_id=p.staff_id,
                                                 location_id=body.location_id, telegram_chat_id=body.telegram_chat_id,
                                                 name=body.name, is_active=body.is_active)
        return _terminal(item)
    except DomainError as exc:
        raise _error(exc) from exc
    except IntegrityError as exc:
        raise _conflict(exc) from exc


@router.patch("/terminals/{terminal_id}")
async def update_terminal(terminal_id: UUID, body: UpdateTerminalRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await service.update_terminal(session, organization_id=p.organization_id, actor_staff_id=p.staff_id,
                                                 terminal_id=terminal_id, location_id=body.location_id,
                                                 telegram_chat_id=body.telegram_chat_id, name=body.name,
                                                 is_active=body.is_active)
        return _terminal(item)
    except DomainError as exc:
        raise _error(exc) from exc
    except IntegrityError as exc:
        raise _conflict(exc) from exc
