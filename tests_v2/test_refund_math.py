from loyalty_v2.application.refund_service import proportional


def test_partial_refund_uses_floor() -> None:
    assert proportional(333, 500, 1000) == 166


def test_final_refund_takes_rounding_remainder() -> None:
    assert proportional(333, 500, 1000, final=True, already=166, already_gross=500) == 167


def test_points_restore_proportionally() -> None:
    assert proportional(300, 2500, 10000) == 75


def test_repeated_partial_refunds_use_cumulative_target() -> None:
    first = proportional(3, 200, 1000, already=0, already_gross=0)
    second = proportional(3, 200, 1000, already=first, already_gross=200)
    third = proportional(3, 200, 1000, already=first + second, already_gross=400)
    assert (first, second, third) == (0, 1, 0)
    assert first + second + third == (3 * 600) // 1000
