from __future__ import annotations

import asyncio
from uuid import UUID

from aiogram import Bot

from loyalty_v2.bots.client_bot import ClientBot
from loyalty_v2.core.config import get_settings
from loyalty_v2.db.session import SessionFactory


async def main() -> None:
    settings = get_settings()
    if not settings.client_bot_token:
        raise RuntimeError("LOYALTY_CLIENT_BOT_TOKEN is required")
    if not settings.organization_id:
        raise RuntimeError("LOYALTY_ORGANIZATION_ID is required")
    bot = Bot(settings.client_bot_token)
    adapter = ClientBot(bot=bot, sessions=SessionFactory, organization_id=UUID(settings.organization_id))
    try:
        await adapter.dispatcher().start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
