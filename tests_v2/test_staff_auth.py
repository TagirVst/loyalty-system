from uuid import uuid4

import pytest

from loyalty_v2.application.auth_service import InvalidPin, Permission, ROLE_PERMISSIONS, StaffAuthService
from loyalty_v2.db.models import StaffRole


def test_pin_must_be_exactly_six_digits() -> None:
    service = StaffAuthService()
    for invalid in ("12345", "1234567", "abcdef", "12 456"):
        with pytest.raises(InvalidPin):
            service.validate_pin_format(invalid)


def test_pin_fingerprint_is_stable_and_org_scoped() -> None:
    service = StaffAuthService()
    org_a, org_b = uuid4(), uuid4()
    assert service.fingerprint(org_a, "123456") == service.fingerprint(org_a, "123456")
    assert service.fingerprint(org_a, "123456") != service.fingerprint(org_b, "123456")


def test_barista_has_no_admin_financial_permission() -> None:
    permissions = ROLE_PERMISSIONS[StaffRole.BARISTA.value]
    assert Permission.SALE_CONFIRM in permissions
    assert Permission.POINTS_ADJUST not in permissions
    assert Permission.ADMIN_ACCESS not in permissions


def test_admin_has_all_declared_permissions() -> None:
    assert ROLE_PERMISSIONS[StaffRole.ADMIN.value] == frozenset(Permission)
