from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError


class IdempotencyKeyReused(DomainError):
    code = "IDEMPOTENCY_KEY_REUSED"


def _lock_key(*, organization_id: UUID, scope: str, key: str) -> int:
    payload = f"{organization_id}:{scope}:{key}".encode("utf-8")
    raw = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(raw, byteorder="big", signed=True)


async def advisory_idempotency_lock(
    session: AsyncSession,
    *,
    organization_id: UUID,
    scope: str,
    key: str,
) -> None:
    normalized = key.strip()
    if not normalized:
        raise IdempotencyKeyReused("Idempotency key cannot be empty")
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _lock_key(organization_id=organization_id, scope=scope, key=normalized)},
    )
