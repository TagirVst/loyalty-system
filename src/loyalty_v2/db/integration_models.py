from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, UUIDPrimaryKeyMixin


class IntegrationClient(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "integration_clients"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_integration_clients_org_name"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    api_key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class IntegrationWebhookInbox(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "integration_webhook_inbox"
    __table_args__ = (
        UniqueConstraint("integration_client_id", "external_event_id", name="uq_integration_webhook_client_event"),
        Index("ix_integration_webhook_status_received", "status", "received_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_client_id: Mapped[UUID] = mapped_column(ForeignKey("integration_clients.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received", index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1000))


class ExternalOrderMapping(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "external_order_mappings"
    __table_args__ = (UniqueConstraint("organization_id", "provider", "external_order_id", name="uq_external_order_mapping"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_order_id: Mapped[str] = mapped_column(String(160), nullable=False)
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders_v2.id", ondelete="SET NULL"), nullable=True, index=True)
    external_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
