from datetime import date

from loyalty_v2.application.reward_service import RewardStatus, birthday_in_year


def test_feb_29_birthday_maps_to_feb_28_in_non_leap_year() -> None:
    assert birthday_in_year(date(2000, 2, 29), 2025) == date(2025, 2, 28)


def test_feb_29_birthday_stays_feb_29_in_leap_year() -> None:
    assert birthday_in_year(date(2000, 2, 29), 2028) == date(2028, 2, 29)


def test_regular_birthday_is_preserved() -> None:
    assert birthday_in_year(date(1990, 9, 10), 2026) == date(2026, 9, 10)


def test_reward_status_contract() -> None:
    assert {s.value for s in RewardStatus} == {"issued", "active", "consumed", "revoked", "expired"}
