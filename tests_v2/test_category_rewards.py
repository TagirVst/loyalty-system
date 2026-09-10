from types import SimpleNamespace

from loyalty_v2.application.reward_engine import RewardCampaignEngine


def test_free_category_item_requires_category_presence() -> None:
    definition = SimpleNamespace(reward_type="free_category_item", config={"category_code": "coffee", "value_minor": 30000})
    try:
        RewardCampaignEngine._reward_discount(definition, 100000, {})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_free_category_item_uses_configured_value() -> None:
    definition = SimpleNamespace(reward_type="free_category_item", config={"category_code": "coffee", "value_minor": 30000})
    assert RewardCampaignEngine._reward_discount(definition, 100000, {"coffee": 2}) == 30000


def test_category_discount_multiplies_by_count() -> None:
    definition = SimpleNamespace(reward_type="category_discount", config={"category_code": "dessert", "amount_per_item_minor": 5000})
    assert RewardCampaignEngine._reward_discount(definition, 100000, {"dessert": 3}) == 15000


def test_campaign_category_minimum_count() -> None:
    campaign = SimpleNamespace(conditions={"category_code": "coffee", "minimum_category_count": 2})
    assert not RewardCampaignEngine._campaign_matches(campaign, 100000, {"coffee": 1})
    assert RewardCampaignEngine._campaign_matches(campaign, 100000, {"coffee": 2})
