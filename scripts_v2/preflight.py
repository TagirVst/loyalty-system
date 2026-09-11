from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from loyalty_v2.api.system_routes import LATEST_SCHEMA_REVISION
from loyalty_v2.core.config import get_settings
from loyalty_v2.db.session import SessionFactory


async def main() -> int:
    settings = get_settings()
    problems: list[str] = []

    if settings.environment.lower() in {"production", "prod"}:
        if settings.organization_id is None and (settings.client_bot_token or settings.staff_bot_token):
            problems.append("LOYALTY_ORGANIZATION_ID is required when a Telegram bot is enabled")
        if settings.sql_echo:
            problems.append("LOYALTY_SQL_ECHO must be false in production")

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
            revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    except Exception as exc:
        problems.append(f"database connectivity/schema check failed: {type(exc).__name__}: {exc}")
    else:
        if revision != LATEST_SCHEMA_REVISION:
            problems.append(f"database schema is {revision!r}, expected {LATEST_SCHEMA_REVISION!r}")

    if problems:
        for problem in problems:
            print(f"PRECHECK FAILED: {problem}", file=sys.stderr)
        return 1

    print("PRECHECK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
