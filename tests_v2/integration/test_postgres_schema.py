from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


def _url() -> str:
    url = os.getenv("LOYALTY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("LOYALTY_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return url


@pytest.mark.asyncio
async def test_database_is_postgresql_and_at_head() -> None:
    engine = create_async_engine(_url())
    try:
        async with engine.connect() as connection:
            dialect = connection.dialect.name
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert dialect == "postgresql"
        assert revision == "0027_notification_delivery_lease"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_required_partial_unique_indexes_exist() -> None:
    engine = create_async_engine(_url())
    names = {
        "uq_identification_active_code_scope",
        "uq_identification_active_customer_scope",
        "uq_points_ledger_entries_org_idempotency",
        "uq_notification_outbox_org_idempotency",
    }
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()"))
            actual = {row[0] for row in rows}
        assert names.issubset(actual)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_points_account_debt_constraints_exist() -> None:
    engine = create_async_engine(_url())
    try:
        async with engine.connect() as connection:
            columns = await connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='points_accounts'"))
            names = {row[0] for row in columns}
        assert {"balance", "debt", "version"}.issubset(names)
    finally:
        await engine.dispose()
