from loyalty_v2.db.milestone_models import CustomerCategoryCounter, MilestoneIssuance, MilestoneRewardRule


def test_counter_tracks_lifetime_and_refund_adjusted_net_values() -> None:
    names = set(CustomerCategoryCounter.__table__.columns.keys())
    assert {"lifetime_count", "net_count", "version"}.issubset(names)


def test_milestone_issuance_has_duplicate_guard_key() -> None:
    names = {c.name for c in MilestoneIssuance.__table__.constraints if getattr(c, "name", None)}
    assert "uq_milestone_issuance_once" in names


def test_rule_supports_repeatable_milestones() -> None:
    names = set(MilestoneRewardRule.__table__.columns.keys())
    assert {"threshold_count", "repeatable", "reward_definition_id"}.issubset(names)
