from pathlib import Path

from loyalty_v2.db.order_models import IdentificationSession


def test_only_one_active_code_per_customer_and_fingerprint_scope() -> None:
    indexes = {idx.name: idx for idx in IdentificationSession.__table__.indexes}
    by_code = indexes["uq_identification_active_code_scope"]
    by_customer = indexes["uq_identification_active_customer_scope"]
    assert by_code.unique is True
    assert by_customer.unique is True
    assert {column.name for column in by_code.columns} == {"organization_id", "code_fingerprint"}
    assert {column.name for column in by_customer.columns} == {"organization_id", "customer_id"}


def test_plaintext_identification_code_is_not_persisted_by_service() -> None:
    text = Path("src/loyalty_v2/application/order_service.py").read_text()
    assert "hmac.new" in text
    assert "code_fingerprint=fingerprint" in text
    assert "code=None" in text
    assert "IdentificationCodeResult" in text
    assert "identification_code_secret" in text
