from pathlib import Path

from loyalty_v2.db.integration_models import ExternalOrderMapping, IntegrationClient, IntegrationWebhookInbox
from loyalty_v2.db.migration_models import LegacyCustomerMapping, MigrationRun


def test_integration_clients_store_only_key_fingerprint() -> None:
    columns = IntegrationClient.__table__.columns
    assert "api_key_fingerprint" in columns
    assert "api_key" not in columns


def test_webhook_inbox_is_idempotent_per_client_event() -> None:
    constraints = {c.name for c in IntegrationWebhookInbox.__table__.constraints if c.name}
    assert "uq_integration_webhook_client_event" in constraints


def test_external_order_mapping_is_provider_scoped() -> None:
    constraints = {c.name for c in ExternalOrderMapping.__table__.constraints if c.name}
    assert "uq_external_order_mapping" in constraints


def test_integration_service_uses_hmac_fingerprint() -> None:
    text = Path("src/loyalty_v2/application/integration_service.py").read_text()
    assert "hmac.new" in text
    assert "integration_api_key_secret" in text
    assert "token_urlsafe(32)" in text


def test_migration_tracks_runs_and_source_mapping() -> None:
    assert "stats" in MigrationRun.__table__.columns
    assert "errors" in MigrationRun.__table__.columns
    assert "source_customer_id" in LegacyCustomerMapping.__table__.columns
    assert "opening_balance" in LegacyCustomerMapping.__table__.columns


def test_v1_import_is_dry_run_by_default_and_uses_ledger_opening_balance() -> None:
    cli = Path("scripts_v2/migrate_v1.py").read_text()
    service = Path("src/loyalty_v2/application/v1_migration_service.py").read_text()
    assert 'parser.add_argument("--apply", action="store_true"' in cli
    assert "service.dry_run" in cli
    assert "LedgerEntryType.MIGRATION" in service
    assert "opening-balance" in service
    assert 'run.status = "blocked"' in service
