from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from loyalty_v2.api.schemas import AdjustPointsRequest, RegisterCustomerRequest
from loyalty_v2.application.services import InvalidPointsAmount, PointsService


def test_register_customer_schema() -> None:
    payload = RegisterCustomerRequest(
        organization_id=uuid4(),
        telegram_id=123456789,
        first_name="Tagir",
        phone="+79990000000",
        birth_date=date(1995, 1, 1),
    )
    assert payload.telegram_id == 123456789


def test_adjustment_requires_reason() -> None:
    with pytest.raises(ValidationError):
        AdjustPointsRequest(
            organization_id=uuid4(), delta=100, reason="", idempotency_key="test-1"
        )


@pytest.mark.asyncio
async def test_points_service_rejects_zero_before_db_access() -> None:
    service = PointsService()
    with pytest.raises(InvalidPointsAmount):
        await service.apply(
            None,  # type: ignore[arg-type]
            organization_id=uuid4(),
            customer_id=uuid4(),
            delta=0,
            entry_type=None,  # type: ignore[arg-type]
        )
