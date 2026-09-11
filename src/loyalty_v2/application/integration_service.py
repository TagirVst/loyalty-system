from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError
from loyalty_v2.core.config import get_settings
from loyalty_v2.db.integration_models import IntegrationClient, IntegrationWebhookInbox


class IntegrationAuthError(DomainError):
    code = "INTEGRATION_AUTH_INVALID"


class IntegrationConfigError(DomainError):
    code = "INTEGRATION_CONFIG_INVALID"


@dataclass(frozen=True, slots=True)
class CreatedIntegrationClient:
    client: IntegrationClient
    api_key: str


class IntegrationService:
    @staticmethod
    def fingerprint(api_key: str) -> str:
        secret = get_settings().integration_api_key_secret.encode("utf-8")
        return hmac.new(secret, api_key.encode("utf-8"), hashlib.sha256).hexdigest()

    async def create_client(self, session: AsyncSession, *, organization_id: UUID, name: str, provider: str) -> CreatedIntegrationClient:
        name = name.strip()
        provider = provider.strip().lower()
        if not name or not provider:
            raise IntegrationConfigError("Integration name and provider are required")
        api_key = secrets.token_urlsafe(32)
        client = IntegrationClient(
            organization_id=organization_id,
            name=name,
            provider=provider,
            api_key_fingerprint=self.fingerprint(api_key),
            is_active=True,
        )
        session.add(client)
        await session.flush()
        return CreatedIntegrationClient(client=client, api_key=api_key)

    async def authenticate(self, session: AsyncSession, *, provider: str, api_key: str) -> IntegrationClient:
        fingerprint = self.fingerprint(api_key.strip())
        client = await session.scalar(select(IntegrationClient).where(
            IntegrationClient.provider == provider.strip().lower(),
            IntegrationClient.api_key_fingerprint == fingerprint,
            IntegrationClient.is_active.is_(True),
        ))
        if client is None:
            raise IntegrationAuthError("Integration API key is invalid")
        return client

    async def ingest_webhook(
        self,
        session: AsyncSession,
        *,
        client: IntegrationClient,
        external_event_id: str,
        event_type: str,
        payload: dict,
    ) -> tuple[IntegrationWebhookInbox, bool]:
        external_event_id = external_event_id.strip()
        event_type = event_type.strip()
        if not external_event_id or not event_type:
            raise IntegrationConfigError("external_event_id and event_type are required")
        existing = await session.scalar(select(IntegrationWebhookInbox).where(
            IntegrationWebhookInbox.integration_client_id == client.id,
            IntegrationWebhookInbox.external_event_id == external_event_id,
        ))
        if existing is not None:
            return existing, False
        item = IntegrationWebhookInbox(
            organization_id=client.organization_id,
            integration_client_id=client.id,
            provider=client.provider,
            external_event_id=external_event_id,
            event_type=event_type,
            payload=payload,
            status="received",
        )
        session.add(item)
        await session.flush()
        return item, True
