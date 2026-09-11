from pathlib import Path


def test_obsolete_insecure_or_duplicate_route_modules_are_removed() -> None:
    assert not Path("src/loyalty_v2/api/routes.py").exists()
    assert not Path("src/loyalty_v2/api/customer_policy_routes.py").exists()
    assert not Path("src/loyalty_v2/api/secure_policy_routes.py").exists()


def test_customer_birth_date_change_uses_customer_principal() -> None:
    text = Path("src/loyalty_v2/api/customer_routes.py").read_text()
    assert '@router.put("/birth-date")' in text
    assert "p = await _principal" in text
    assert "organization_id=p.organization_id" in text
    assert "customer_id=p.customer_id" in text


def test_phone_change_is_not_exposed_as_unverified_http_endpoint() -> None:
    routes = Path("src/loyalty_v2/api/customer_routes.py").read_text()
    bot = Path("src/loyalty_v2/bots/client_bot.py").read_text()
    portal = Path("src/loyalty_v2/application/customer_portal_service.py").read_text()
    assert '@router.put("/phone")' not in routes
    assert "message.contact.user_id != message.from_user.id" in bot
    assert "portal.change_phone" in bot
    assert "policies.change_phone" in portal
