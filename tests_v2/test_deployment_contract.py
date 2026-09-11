from pathlib import Path


def test_v2_image_runs_unprivileged_and_exposes_src_package() -> None:
    text = Path("Dockerfile.v2").read_text()
    assert "PYTHONPATH=/app/src" in text
    assert "USER loyalty" in text
    assert "loyalty_v2.api.app:app" in text


def test_compose_runs_migrations_before_api() -> None:
    text = Path("docker-compose.v2.yml").read_text()
    assert "alembic -c alembic_v2.ini upgrade head" in text
    assert "condition: service_completed_successfully" in text


def test_compose_contains_all_v2_long_running_processes() -> None:
    text = Path("docker-compose.v2.yml").read_text()
    for service in ("api:", "client_bot:", "staff_bot:", "notification_worker:"):
        assert service in text


def test_production_secrets_are_documented() -> None:
    text = Path(".env.v2.example").read_text()
    assert "LOYALTY_PIN_FINGERPRINT_SECRET" in text
    assert "LOYALTY_IDENTIFICATION_CODE_SECRET" in text
    assert "LOYALTY_INTEGRATION_API_KEY_SECRET" in text
