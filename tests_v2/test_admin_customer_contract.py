from loyalty_v2.api.admin_customer_routes import AdjustPointsRequest, BlockRequest, TierOverrideRequest


def test_admin_customer_requests_do_not_accept_organization_id():
    for model in (AdjustPointsRequest, BlockRequest, TierOverrideRequest):
        assert "organization_id" not in model.model_fields
        assert "staff_session_id" in model.model_fields


def test_manual_points_adjustment_requires_reason_and_idempotency():
    fields = AdjustPointsRequest.model_fields
    assert fields["reason"].is_required()
    assert fields["idempotency_key"].is_required()


def test_blocking_requires_reason():
    assert BlockRequest.model_fields["reason"].is_required()
