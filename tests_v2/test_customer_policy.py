from datetime import datetime, timedelta, timezone

import pytest

from loyalty_v2.application.customer_policy_service import CustomerPolicyError, CustomerPolicyService


def test_redemption_override_rejects_percent_over_100() -> None:
    service = CustomerPolicyService()
    with pytest.raises(CustomerPolicyError):
        # Validation happens before DB access.
        import asyncio
        asyncio.run(service.set_redemption_override(None, organization_id=None, customer_id=None, max_percent=101, staff_id=None, reason="test", ends_at=datetime.now(timezone.utc) + timedelta(days=1)))  # type: ignore[arg-type]


def test_redemption_override_requires_future_expiry() -> None:
    service = CustomerPolicyService()
    with pytest.raises(CustomerPolicyError):
        import asyncio
        asyncio.run(service.set_redemption_override(None, organization_id=None, customer_id=None, max_percent=100, staff_id=None, reason="test", ends_at=datetime.now(timezone.utc) - timedelta(seconds=1)))  # type: ignore[arg-type]
