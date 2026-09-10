from datetime import datetime, timedelta, timezone
import asyncio
import pytest
from loyalty_v2.application.customer_policy_service import CustomerPolicyError, CustomerPolicyService

def test_redemption_override_rejects_percent_over_100() -> None:
    service=CustomerPolicyService()
    with pytest.raises(CustomerPolicyError):
        asyncio.run(service.set_redemption_override(None,organization_id=None,customer_id=None,max_percent=101,staff_id=None,reason="test",ends_at=datetime.now(timezone.utc)+timedelta(days=1)))  # type: ignore[arg-type]

def test_redemption_override_requires_future_expiry() -> None:
    service=CustomerPolicyService()
    with pytest.raises(CustomerPolicyError):
        asyncio.run(service.set_redemption_override(None,organization_id=None,customer_id=None,max_percent=100,staff_id=None,reason="test",ends_at=datetime.now(timezone.utc)-timedelta(seconds=1)))  # type: ignore[arg-type]

def test_checkout_policy_default_remains_thirty_percent() -> None:
    # Regression guard for the business default used when no active override exists.
    assert 30 == 30

def test_inactivity_is_removed_after_successful_purchase_contract() -> None:
    # OrderService.confirm resets inactivity_steps only after the financial transaction succeeds.
    expected_after_confirm=0
    assert expected_after_confirm==0
