from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.integration_service import IntegrationAuthError, IntegrationService
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2", tags=["integrations"])
principals = PrincipalService()
integrations = IntegrationService()


class CreateIntegrationClientRequest(BaseModel):
    staff_session_id: UUID
    name: str = Field(min_length=1, max_length=160)
    provider: str = Field(min_length=1, max_length=64)


class WebhookRequest(BaseModel):
    external_event_id: str = Field(min_length=1, max_length=160)
    event_type: str = Field(min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)


def _error(exc: DomainError) -> HTTPException:
    if isinstance(exc, IntegrationAuthError):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": exc.code, "message": str(exc)})
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": str(exc)})


@router.post("/admin/integrations/clients", status_code=201)
async def create_client(body: CreateIntegrationClientRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.ADMIN_ACCESS)
            created = await integrations.create_client(session, organization_id=principal.organization_id, name=body.name, provider=body.provider)
        return {
            "id": created.client.id,
            "name": created.client.name,
            "provider": created.client.provider,
            "api_key": created.api_key,
            "warning": "API key is returned only at creation time",
        }
    except DomainError as exc:
        raise _error(exc) from exc


@router.post("/integrations/webhooks/{provider}")
async def webhook(
    provider: str,
    body: WebhookRequest,
    x_integration_key: str = Header(alias="X-Integration-Key"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        async with session.begin():
            client = await integrations.authenticate(session, provider=provider, api_key=x_integration_key)
            item, created = await integrations.ingest_webhook(
                session,
                client=client,
                external_event_id=body.external_event_id,
                event_type=body.event_type,
                payload=body.payload,
            )
        return {"event_id": item.id, "status": item.status, "accepted": created}
    except DomainError as exc:
        raise _error(exc) from exc
