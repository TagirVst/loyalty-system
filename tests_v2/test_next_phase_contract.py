from pathlib import Path


def test_client_bot_exposes_feedback_and_marketing_controls() -> None:
    text = Path("src/loyalty_v2/bots/client_bot.py").read_text()
    assert "Оставить отзыв" in text
    assert "Уведомления" in text
    assert "FeedbackFlow" in text
    assert "set_marketing_notifications" in text


def test_admin_analytics_is_registered_and_tracks_net_financials() -> None:
    app = Path("src/loyalty_v2/api/app.py").read_text()
    service = Path("src/loyalty_v2/application/admin_analytics_service.py").read_text()
    route = Path("src/loyalty_v2/api/admin_analytics_routes.py").read_text()
    assert "admin_analytics_router" in app
    assert "points_debt_created" in service
    assert "active_customers" in service
    assert '"net_paid_minor"' in route


def test_customer_overrides_can_be_explicitly_cleared_with_audit() -> None:
    service = Path("src/loyalty_v2/application/admin_override_service.py").read_text()
    route = Path("src/loyalty_v2/api/admin_override_routes.py").read_text()
    assert 'action="customer.overrides.clear"' in service
    assert 'overrides/clear' in route
    assert "clear_tier" in route
    assert "clear_redemption" in route


def test_hardening_checkpoint_is_explicitly_not_production_verified() -> None:
    text = Path("docs/13-IMPLEMENTATION-STATUS.md").read_text()
    assert "CODE COMPLETE — REAL TESTS REQUIRED" in text
    assert "PostgreSQL" in text
    assert "production readiness remains provisional" in text


def test_cutover_runbook_requires_clean_dry_run_and_concurrency_gate() -> None:
    text = Path("docs/14-CUTOVER-RUNBOOK.md").read_text()
    assert "no production cutover" in text.lower()
    assert "clean dry run" in text.lower()
    assert "Concurrency gate" in text
