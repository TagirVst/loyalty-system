from pathlib import Path


def test_customer_rewards_snapshot_definition_semantics():
    models = Path("src/loyalty_v2/db/reward_models.py").read_text()
    service = Path("src/loyalty_v2/application/reward_service.py").read_text()
    engine = Path("src/loyalty_v2/application/reward_engine.py").read_text()
    order = Path("src/loyalty_v2/application/order_service.py").read_text()
    assert "reward_definition_version" in models
    assert "definition_snapshot" in models
    assert "definition_snapshot=self.definition_snapshot(definition)" in service
    assert "cr.definition_snapshot" in engine
    assert '"reward_definition_version":x.reward_definition_version' in order


def test_milestone_refunds_use_issuance_snapshot():
    models = Path("src/loyalty_v2/db/milestone_models.py").read_text()
    service = Path("src/loyalty_v2/application/milestone_service.py").read_text()
    assert "threshold_count_snapshot" in models
    assert "rule_version" in models
    assert "issuance.threshold_count_snapshot" in service
    assert "issuance.milestone_number * rule.threshold_count" not in service


def test_semantic_config_updates_increment_version():
    text = Path("src/loyalty_v2/application/admin_config_service.py").read_text()
    assert "item.config_version += 1" in text
    assert "semantic_changed" in text


def test_order_and_refund_idempotency_are_serialized_and_scope_checked():
    helper = Path("src/loyalty_v2/application/idempotency.py").read_text()
    order = Path("src/loyalty_v2/application/order_service.py").read_text()
    refund = Path("src/loyalty_v2/application/refund_service.py").read_text()
    assert "pg_advisory_xact_lock" in helper
    assert 'scope="order_confirm"' in order
    assert 'scope="refund_confirm"' in refund
    assert "IdempotencyKeyReused" in order
    assert "IdempotencyKeyReused" in refund
    assert "existing.draft_id!=draft_id" in order
    assert "existing.order_id!=order_id" in refund
