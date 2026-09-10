from types import SimpleNamespace
from uuid import uuid4

from loyalty_v2.application.reward_engine import RewardCampaignEngine


def test_fixed_reward_discount_is_capped_by_order_total() -> None:
    definition = SimpleNamespace(reward_type="fixed_discount", config={"amount_minor": 50000})
    assert RewardCampaignEngine._reward_discount(definition, 12000) == 12000


def test_percent_reward_discount_uses_integer_math() -> None:
    definition = SimpleNamespace(reward_type="percent_discount", config={"percent": 15})
    assert RewardCampaignEngine._reward_discount(definition, 100_00) == 1500


def test_campaign_spend_conditions() -> None:
    campaign = SimpleNamespace(conditions={"minimum_spend_minor": 10000, "maximum_spend_minor": 30000})
    assert RewardCampaignEngine._campaign_matches(campaign, 15000)
    assert not RewardCampaignEngine._campaign_matches(campaign, 5000)
    assert not RewardCampaignEngine._campaign_matches(campaign, 40000)


def test_unknown_reward_type_has_no_monetary_effect() -> None:
    definition = SimpleNamespace(reward_type="future_custom", config={"value_minor": 10000})
    assert RewardCampaignEngine._reward_discount(definition, 20000) == 0
