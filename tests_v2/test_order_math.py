from loyalty_v2.application.order_service import DEFAULT_REDEMPTION_PERCENT, POINT_MINOR_VALUE


def test_standard_redemption_limit_for_1000_rub() -> None:
    amount_minor = 100_000
    max_points = (amount_minor * DEFAULT_REDEMPTION_PERCENT) // (100 * POINT_MINOR_VALUE)
    assert max_points == 300


def test_gold_cashback_7_percent_for_1000_rub() -> None:
    paid_minor = 100_000
    cashback_basis_points = 700
    points = (paid_minor * cashback_basis_points) // 1_000_000
    assert points == 70


def test_cashback_floor_rounding() -> None:
    paid_minor = 12_345
    cashback_basis_points = 300
    points = (paid_minor * cashback_basis_points) // 1_000_000
    assert points == 3


def test_any_redemption_means_zero_cashback() -> None:
    redeemed_points = 1
    paid_minor = 99_900
    cashback_basis_points = 1_000
    points = 0 if redeemed_points else (paid_minor * cashback_basis_points) // 1_000_000
    assert points == 0
