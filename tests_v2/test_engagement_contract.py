from loyalty_v2.application.reward_engine import RewardCampaignEngine
from loyalty_v2.application.segment_service import SegmentService


def test_segment_category_count_condition():
    class State:
        qualification_spend_minor = 50_000
        last_purchase_at = None
    class Account:
        balance = 10
    class Tier:
        name = "Gold"
    from datetime import datetime, timezone
    assert SegmentService.matches(
        {"minimum_qualification_spend_minor": 10_000, "tier_names": ["gold"], "category_counts": {"coffee": 10}},
        state=State(), account=Account(), tier=Tier(), category_counts={"coffee": 12}, now=datetime.now(timezone.utc),
    )


def test_campaign_requires_all_segment_codes():
    class Campaign:
        conditions = {"segment_codes": ["vip", "coffee10"]}
    assert RewardCampaignEngine._campaign_matches(Campaign(), 1000, {}, {"vip", "coffee10"})
    assert not RewardCampaignEngine._campaign_matches(Campaign(), 1000, {}, {"vip"})


def test_campaign_without_segments_remains_compatible():
    class Campaign:
        conditions = {"minimum_spend_minor": 500}
    assert RewardCampaignEngine._campaign_matches(Campaign(), 1000, {}, set())
