from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.reconciliation_service import ReconciliationService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.notification_models import NotificationOutbox
from loyalty_v2.db.session import get_session

LATEST_SCHEMA_REVISION = "0027_notification_delivery_lease"
router = APIRouter(tags=["system"])
principals = PrincipalService()
reconciliation = ReconciliationService()


async def _admin(session: AsyncSession, staff_session_id: UUID):
    try:
        principal = await principals.staff(session, staff_session_id=staff_session_id)
        principal.require(Permission.ADMIN_ACCESS)
        return principal
    except DomainError as exc:
        code = status.HTTP_403_FORBIDDEN if exc.code == "PERMISSION_DENIED" else status.HTTP_401_UNAUTHORIZED
        raise HTTPException(code, detail={"code": exc.code, "message": str(exc)}) from exc


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "loyalty-v2"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        await session.execute(text("SELECT 1"))
        revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "not_ready", "database": "unavailable"}) from exc
    if revision != LATEST_SCHEMA_REVISION:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "not_ready", "database": "ok", "schema_revision": revision, "expected_revision": LATEST_SCHEMA_REVISION})
    return {"status": "ready", "database": "ok", "schema_revision": revision}


@router.get("/ops/status")
async def operational_status(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    principal = await _admin(session, staff_session_id)
    now = datetime.now(timezone.utc)
    counts = dict((await session.execute(select(NotificationOutbox.status, func.count(NotificationOutbox.id)).where(NotificationOutbox.organization_id == principal.organization_id).group_by(NotificationOutbox.status))).all())
    overdue = await session.scalar(select(func.count(NotificationOutbox.id)).where(NotificationOutbox.organization_id == principal.organization_id, NotificationOutbox.status.in_(["queued", "retry"]), NotificationOutbox.next_attempt_at < now))
    expired_leases = await session.scalar(select(func.count(NotificationOutbox.id)).where(NotificationOutbox.organization_id == principal.organization_id, NotificationOutbox.status == "processing", NotificationOutbox.lease_until < now))
    return {"status": "ok", "notifications": {"by_status": {str(key): int(value) for key, value in counts.items()}, "overdue": int(overdue or 0), "expired_leases": int(expired_leases or 0)}}


@router.get("/ops/reconcile")
async def reconcile(staff_session_id: UUID, limit: int = Query(default=10000, ge=1, le=100000), session: AsyncSession = Depends(get_session)) -> dict:
    principal = await _admin(session, staff_session_id)
    report = await reconciliation.run(session, organization_id=principal.organization_id, limit=limit)
    return {
        "ok": report.ok,
        "organization_id": report.organization_id,
        "checked_accounts": report.checked_accounts,
        "checked_orders": report.checked_orders,
        "issue_count": len(report.issues),
        "issues": [{"code": x.code, "object_type": x.object_type, "object_id": x.object_id, "details": x.details} for x in report.issues],
    }
