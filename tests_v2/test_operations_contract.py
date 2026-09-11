from pathlib import Path


def test_readiness_checks_database_and_schema_revision() -> None:
    text = Path("src/loyalty_v2/api/system_routes.py").read_text()
    assert '@router.get("/ready")' in text
    assert 'SELECT version_num FROM alembic_version' in text
    assert 'LATEST_SCHEMA_REVISION = "0027_notification_delivery_lease"' in text
    assert 'HTTP_503_SERVICE_UNAVAILABLE' in text


def test_operational_status_is_admin_and_tenant_scoped() -> None:
    text = Path("src/loyalty_v2/api/system_routes.py").read_text()
    assert "Permission.ADMIN_ACCESS" in text
    assert "NotificationOutbox.organization_id == principal.organization_id" in text


def test_external_order_location_is_tenant_scoped() -> None:
    text = Path("src/loyalty_v2/application/integration_order_service.py").read_text()
    assert "Location.organization_id == client.organization_id" in text
    assert "Location.is_active.is_(True)" in text


def test_backup_and_restore_have_safety_guards() -> None:
    backup = Path("scripts_v2/backup_postgres.sh").read_text()
    restore = Path("scripts_v2/restore_postgres.sh").read_text()
    assert "pg_dump" in backup
    assert "pg_restore --list" in backup
    assert 'ALLOW_DESTRUCTIVE_RESTORE' in restore
    assert 'refusing destructive restore' in restore


def test_compose_health_uses_readiness_not_liveness() -> None:
    text = Path("docker-compose.v2.yml").read_text()
    assert 'http://localhost:8000/ready' in text
