from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.integration_service import IntegrationConfigError
from loyalty_v2.application.order_service import IdentificationService, OrderService
from loyalty_v2.db.integration_models import ExternalOrderMapping, IntegrationClient, IntegrationWebhookInbox


@dataclass(frozen=True, slots=True)
class NormalizedExternalOrder:
    external_order_id: str
    location_id: UUID
    customer_code: str
    gross_amount_minor: int
    requested_points: int = 0
    currency_code: str = "RUB"
    category_counts: dict[str, int] | None = None


class ExternalOrderAdapter(Protocol):
    def supports(self, event_type: str) -> bool: ...
    def normalize(self, payload: dict) -> NormalizedExternalOrder: ...


class GenericOrderAdapter:
    def supports(self, event_type: str) -> bool:
        return event_type == "order.confirm"

    def normalize(self, payload: dict) -> NormalizedExternalOrder:
        try:
            external_order_id = str(payload["external_order_id"]).strip()
            location_id = UUID(str(payload["location_id"]))
            customer_code = str(payload["customer_code"]).strip()
            gross = int(payload["gross_amount_minor"])
            requested = int(payload.get("requested_points", 0))
            currency = str(payload.get("currency_code", "RUB")).strip().upper()
            categories = {str(k): int(v) for k, v in (payload.get("category_counts") or {}).items() if int(v) > 0}
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationConfigError("External order payload is invalid") from exc
        if not external_order_id or len(customer_code) != 5 or not customer_code.isdigit() or gross <= 0 or requested < 0:
            raise IntegrationConfigError("External order payload is invalid")
        return NormalizedExternalOrder(external_order_id, location_id, customer_code, gross, requested, currency, categories)


class IntegrationOrderService:
    def __init__(self) -> None:
        self.orders = OrderService()
        self.identification = IdentificationService()
        self.adapters: dict[str, ExternalOrderAdapter] = {"generic": GenericOrderAdapter()}

    def adapter_for(self, provider: str) -> ExternalOrderAdapter:
        adapter = self.adapters.get(provider)
        if adapter is None:
            raise IntegrationConfigError(f"Provider adapter is not configured: {provider}")
        return adapter

    async def process(self, session: AsyncSession, *, client: IntegrationClient, inbox: IntegrationWebhookInbox):
        if inbox.status == "processed":
            mapping = await session.scalar(select(ExternalOrderMapping).where(
                ExternalOrderMapping.organization_id == client.organization_id,
                ExternalOrderMapping.provider == client.provider,
                ExternalOrderMapping.external_payload["event_id"].as_string() == str(inbox.id),
            ))
            return mapping
        adapter = self.adapter_for(client.provider)
        if not adapter.supports(inbox.event_type):
            raise IntegrationConfigError("Webhook event type is not supported by provider adapter")
        normalized = adapter.normalize(inbox.payload)
        existing = await session.scalar(select(ExternalOrderMapping).where(
            ExternalOrderMapping.organization_id == client.organization_id,
            ExternalOrderMapping.provider == client.provider,
            ExternalOrderMapping.external_order_id == normalized.external_order_id,
        ).with_for_update())
        if existing is not None and existing.order_id is not None:
            inbox.status = "processed"
            return existing

        draft = await self.orders.create_draft(
            session,
            organization_id=client.organization_id,
            location_id=normalized.location_id,
            gross_amount_minor=normalized.gross_amount_minor,
            requested_points=normalized.requested_points,
            currency_code=normalized.currency_code,
            category_counts=normalized.category_counts,
        )
        await self.identification.attach_to_draft(session, organization_id=client.organization_id, draft_id=draft.id, code=normalized.customer_code)
        quote = await self.orders.quote(session, organization_id=client.organization_id, draft_id=draft.id)
        order = await self.orders.confirm(
            session,
            organization_id=client.organization_id,
            draft_id=draft.id,
            quote_id=quote.quote.id,
            idempotency_key=f"integration:{client.id}:{normalized.external_order_id}",
        )
        mapping = existing or ExternalOrderMapping(
            organization_id=client.organization_id,
            provider=client.provider,
            external_order_id=normalized.external_order_id,
            external_payload={"event_id": str(inbox.id), "payload": inbox.payload},
        )
        mapping.order_id = order.id
        if existing is None:
            session.add(mapping)
        inbox.status = "processed"
        await session.flush()
        return mapping
