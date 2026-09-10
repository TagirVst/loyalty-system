from loyalty_v2.application.refund_service import proportional


def test_partial_refund_uses_floor() -> None:
    assert proportional(333, 500, 1000) == 166


def test_final_refund_takes_rounding_remainder() -> None:
    assert proportional(333, 500, 1000, final=True, already=166) == 167


def test_points_restore_proportionally() -> None:
    assert proportional(300, 2500, 10000) == 75
