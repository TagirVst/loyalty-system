from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from loyalty_v2.core.config import get_settings
from loyalty_v2.db.base import Base
from loyalty_v2.db import audit_models  # noqa: F401
from loyalty_v2.db import auth_models  # noqa: F401
from loyalty_v2.db import category_models  # noqa: F401
from loyalty_v2.db import customer_auth_models  # noqa: F401
from loyalty_v2.db import customer_policy_models  # noqa: F401
from loyalty_v2.db import engagement_models  # noqa: F401
from loyalty_v2.db import identity_models  # noqa: F401
from loyalty_v2.db import integration_models  # noqa: F401
from loyalty_v2.db import migration_models  # noqa: F401
from loyalty_v2.db import milestone_models  # noqa: F401
from loyalty_v2.db import models  # noqa: F401
from loyalty_v2.db import notification_models  # noqa: F401
from loyalty_v2.db import notification_template_models  # noqa: F401
from loyalty_v2.db import order_models  # noqa: F401
from loyalty_v2.db import refund_models  # noqa: F401
from loyalty_v2.db import reward_models  # noqa: F401

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction(): context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction(): context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection: await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None: asyncio.run(run_async_migrations())

if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
