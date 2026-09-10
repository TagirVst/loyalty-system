from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.db.audit_models import AuditLog


class AuditService:
    async def record(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        actor_staff_id: UUID | None,
        action: str,
        object_type: str,
        object_id: UUID | None,
        before: dict | None = None,
        after: dict | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        item = AuditLog(
            organization_id=organization_id,
            actor_staff_id=actor_staff_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before=self.jsonable(before),
            after=self.jsonable(after),
            metadata_json=self.jsonable(metadata or {}),
        )
        session.add(item)
        await session.flush()
        return item

    @classmethod
    def snapshot(cls, obj, fields: tuple[str, ...]) -> dict:
        return cls.jsonable({field: getattr(obj, field) for field in fields})

    @classmethod
    def jsonable(cls, value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(k): cls.jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls.jsonable(v) for v in value]
        return str(value)
