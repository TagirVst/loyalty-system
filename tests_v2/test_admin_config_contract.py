import pytest

from loyalty_v2.api.admin_config_routes import (
    CreateCampaignRequest,
    CreateCategoryRequest,
    CreateMilestoneRequest,
    CreateRewardRequest,
)
from loyalty_v2.application.admin_config_service import AdminConfigService, ConfigInvalid


def test_admin_config_requests_do_not_accept_organization_scope() -> None:
    for model in (CreateCategoryRequest, CreateRewardRequest, CreateCampaignRequest, CreateMilestoneRequest):
        assert "organization_id" not in model.model_fields
        assert "staff_session_id" in model.model_fields


def test_codes_are_normalized_and_restricted() -> None:
    assert AdminConfigService._code(" Coffee-6 ") == "coffee-6"
    with pytest.raises(ConfigInvalid):
        AdminConfigService._code("кофе №6")


def test_reward_types_are_allowlisted() -> None:
    AdminConfigService._validate_reward("free_category_item", {"category_code": "coffee"}, 7)
    with pytest.raises(ConfigInvalid):
        AdminConfigService._validate_reward("python_expression", {}, None)


def test_campaign_window_must_be_ordered() -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    with pytest.raises(ConfigInvalid):
        AdminConfigService._validate_campaign(10, now, now)
