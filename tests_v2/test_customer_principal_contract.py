from pathlib import Path


def test_customer_session_model_has_identity_scope():
    text = Path("src/loyalty_v2/db/customer_auth_models.py").read_text()
    assert "class CustomerSession" in text
    assert "identity_id" in text
    assert "external_session_key" in text
    assert "expires_at" in text


def test_customer_principal_does_not_trust_request_identity():
    text = Path("src/loyalty_v2/api/customer_routes.py").read_text()
    assert "CustomerPrincipal" not in text or "principals.customer" in text
    assert "organization_id: UUID" not in text
    assert "external_subject" not in text
    assert "customer_session_id" in text


def test_feedback_uses_customer_principal_scope():
    text = Path("src/loyalty_v2/api/customer_routes.py").read_text()
    assert "organization_id=p.organization_id" in text
    assert "customer_id=p.customer_id" in text
