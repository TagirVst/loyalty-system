from pathlib import Path


def test_obsolete_insecure_route_modules_are_removed() -> None:
    assert not Path("src/loyalty_v2/api/routes.py").exists()
    assert not Path("src/loyalty_v2/api/customer_policy_routes.py").exists()


def test_customer_profile_changes_use_customer_principal() -> None:
    text = Path("src/loyalty_v2/api/customer_routes.py").read_text()
    assert '@router.put("/phone")' in text
    assert '@router.put("/birth-date")' in text
    assert "p = await _principal" in text
    assert "organization_id=p.organization_id" in text
    assert "customer_id=p.customer_id" in text
