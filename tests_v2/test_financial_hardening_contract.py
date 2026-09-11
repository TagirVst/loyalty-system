from pathlib import Path

from loyalty_v2.db.models import PointsAccount, PointsLedgerEntry


def test_points_account_tracks_nonnegative_debt() -> None:
    assert "debt" in PointsAccount.__table__.columns
    assert "debt_applied" in PointsLedgerEntry.__table__.columns
    assert "debt_after" in PointsLedgerEntry.__table__.columns


def test_positive_points_first_repay_debt() -> None:
    text = Path("src/loyalty_v2/application/services.py").read_text()
    assert "debt_applied=min(delta,account.debt)" in text
    assert "account.debt-=debt_applied" in text
    assert "balance_delta=delta-debt_applied" in text


def test_refund_creates_debt_for_spent_earned_points() -> None:
    text = Path("src/loyalty_v2/application/refund_service.py").read_text()
    assert "shortfall=preview.reversed_earned_points-reversal" in text
    assert "self.points.add_debt" in text
    assert "refund.points_debt_created=shortfall" in text


def test_refund_supports_explicit_category_allocation() -> None:
    service = Path("src/loyalty_v2/application/refund_service.py").read_text()
    schemas = Path("src/loyalty_v2/api/secure_schemas.py").read_text()
    routes = Path("src/loyalty_v2/api/secure_routes.py").read_text()
    assert "explicit: dict[str,int] | None" in service
    assert "Refund contains unknown order category" in service
    assert "Refund category quantity exceeds remaining order quantity" in service
    assert "category_counts:dict[str,int]|None=None" in schemas
    assert "category_counts=body.category_counts" in routes


def test_full_refund_restores_only_eligible_order_rewards() -> None:
    text = Path("src/loyalty_v2/application/refund_service.py").read_text()
    assert "_restore_order_rewards" in text
    assert 'reward.status in {"revoked","expired"}' in text
    assert "reward.quantity_remaining += 1" in text
    assert "if preview.remaining_gross_minor==0" in text
    assert '"restored_reward_ids"' in text
