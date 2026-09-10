from __future__ import annotations

import asyncio

from aiogram import Bot

from loyalty_v2.application.notification_service import NotificationService
from loyalty_v2.application.telegram_notification_provider import TelegramNotificationProvider
from loyalty_v2.core.config import get_settings
from loyalty_v2.db.session import SessionFactory


async def run_forever(*, poll_seconds: float = 2.0) -> None:
    settings = get_settings()
    if not settings.client_bot_token:
        raise RuntimeError("LOYALTY_CLIENT_BOT_TOKEN is required")
    bot = Bot(settings.client_bot_token)
    provider = TelegramNotificationProvider(bot)
    service = NotificationService()
    try:
        while True:
            async with SessionFactory() as session:
                async with session.begin():
                    result = await service.deliver_due(session, provider=provider, limit=100)
            if result.sent == 0 and result.retried == 0 and result.failed == 0:
                await asyncio.sleep(poll_seconds)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_forever())
