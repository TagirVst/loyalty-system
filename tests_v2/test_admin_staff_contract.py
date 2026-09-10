from loyalty_v2.api.admin_staff_routes import (
    ChangePinRequest,
    CreateStaffRequest,
    CreateTerminalRequest,
    UpdateStaffRequest,
)
from loyalty_v2.db.auth_models import StaffSession


def test_staff_requests_do_not_accept_organization_id() -> None:
    for model in (CreateStaffRequest, CreateTerminalRequest, UpdateStaffRequest, ChangePinRequest):
        assert "organization_id" not in model.model_fields
        assert "staff_session_id" in model.model_fields


def test_staff_pin_is_six_digits() -> None:
    field = CreateStaffRequest.model_fields["pin"]
    assert field is not None


def test_active_terminal_session_has_unique_partial_index() -> None:
    indexes = {idx.name: idx for idx in StaffSession.__table__.indexes}
    idx = indexes["uq_staff_sessions_active_terminal"]
    assert idx.unique is True
    assert {column.name for column in idx.columns} == {"terminal_id"}


def test_staff_response_contract_never_exposes_pin_material() -> None:
    forbidden = {"pin", "pin_hash", "pin_fingerprint"}
    assert forbidden.isdisjoint({"id", "location_id", "name", "role", "is_active", "pin_configured"})
