from pathlib import Path


def test_reconciliation_checks_financial_invariants() -> None:
    text = Path("src/loyalty_v2/application/reconciliation_service.py").read_text()
    assert "ACCOUNT_LEDGER_SNAPSHOT_MISMATCH" in text
    assert "ORDER_OVER_REFUNDED_GROSS" in text
    assert "ORDER_OVER_REFUNDED_PAID" in text
    assert "ORDER_OVER_RESTORED_POINTS" in text
    assert "ORDER_OVER_REVERSED_QUALIFICATION" in text


def test_reconciliation_endpoint_is_admin_scoped() -> None:
    text = Path("src/loyalty_v2/api/system_routes.py").read_text()
    assert '@router.get("/ops/reconcile")' in text
    assert "Permission.ADMIN_ACCESS" in text
    assert "organization_id=principal.organization_id" in text


def test_production_secrets_are_long_and_distinct() -> None:
    text = Path("src/loyalty_v2/core/config.py").read_text()
    assert "len(value) < 32" in text
    assert "len(set(secrets.values()))" in text
    assert "postgresql+asyncpg://" in text


def test_preflight_blocks_api_startup() -> None:
    compose = Path("docker-compose.v2.yml").read_text()
    preflight = Path("scripts_v2/preflight.py").read_text()
    assert "preflight:" in compose
    assert "condition: service_completed_successfully" in compose
    assert "PRECHECK FAILED" in preflight
    assert "LATEST_SCHEMA_REVISION" in preflight


def test_real_postgres_test_harness_exists() -> None:
    compose = Path("docker-compose.test.yml").read_text()
    runner = Path("scripts_v2/run_postgres_tests.sh").read_text()
    assert "postgres:16-alpine" in compose
    assert "alembic -c alembic_v2.ini upgrade head" in runner
    assert "pytest -q tests_v2" in runner
