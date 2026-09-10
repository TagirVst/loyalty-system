from loyalty_v2.api.secure_schemas import CreateDraftRequest, ConfirmOrderRequest, RefundPreviewRequest


def test_cashier_requests_do_not_accept_tenant_scope() -> None:
    for model in (CreateDraftRequest, ConfirmOrderRequest, RefundPreviewRequest):
        fields = model.model_fields
        assert "organization_id" not in fields
        assert "location_id" not in fields


def test_staff_session_is_required_for_cashier_requests() -> None:
    for model in (CreateDraftRequest, ConfirmOrderRequest, RefundPreviewRequest):
        assert "staff_session_id" in model.model_fields
