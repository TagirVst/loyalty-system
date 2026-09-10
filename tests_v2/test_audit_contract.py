from datetime import datetime, timezone
from uuid import uuid4

from loyalty_v2.application.audit_service import AuditService
from loyalty_v2.db.audit_models import AuditLog


def test_audit_jsonable_handles_domain_values() -> None:
    uid = uuid4()
    now = datetime.now(timezone.utc)
    result = AuditService.jsonable({"id": uid, "when": now, "nested": [uid]})
    assert result["id"] == str(uid)
    assert result["when"] == now.isoformat()
    assert result["nested"] == [str(uid)]


def test_audit_log_has_before_after_snapshots() -> None:
    assert hasattr(AuditLog, "before")
    assert hasattr(AuditLog, "after")
    assert hasattr(AuditLog, "actor_staff_id")
