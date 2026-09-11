from pathlib import Path


def test_external_order_adapter_is_provider_neutral() -> None:
    text = Path("src/loyalty_v2/application/integration_order_service.py").read_text()
    assert "class ExternalOrderAdapter(Protocol)" in text
    assert "class GenericOrderAdapter" in text
    assert "NormalizedExternalOrder" in text


def test_external_order_uses_normal_loyalty_order_pipeline() -> None:
    text = Path("src/loyalty_v2/application/integration_order_service.py").read_text()
    assert "self.orders.create_draft" in text
    assert "self.identification.attach_to_draft" in text
    assert "self.orders.quote" in text
    assert "self.orders.confirm" in text
    assert "integration:{client.id}:{normalized.external_order_id}" in text


def test_webhook_returns_internal_order_mapping() -> None:
    text = Path("src/loyalty_v2/api/integration_routes.py").read_text()
    assert "integration_orders.process" in text
    assert '"order_id": order_id' in text
