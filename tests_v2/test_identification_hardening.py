from loyalty_v2.db.order_models import IdentificationSession


def test_only_one_active_code_per_customer_and_code_scope() -> None:
    indexes = {idx.name: idx for idx in IdentificationSession.__table__.indexes}
    by_code = indexes["uq_identification_active_code_scope"]
    by_customer = indexes["uq_identification_active_customer_scope"]
    assert by_code.unique is True
    assert by_customer.unique is True
    assert {column.name for column in by_code.columns} == {"organization_id", "code"}
    assert {column.name for column in by_customer.columns} == {"organization_id", "customer_id"}
