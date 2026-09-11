from __future__ import annotations

import asyncio

from aiogram import Bot

from loyalty_v2.application.notification_service import DeliveryBatchResult, NotificationService
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
                    claimed = await service.claim_due(session, limit=100)
            if not claimed:
                await asyncio.sleep(poll_seconds)
                continue
            for item in claimed:
                error: Exception | None = None
                if item.recipient is None:
                    error = RuntimeError("No active verified delivery identity")
                else:
                    try:
                        await provider.send(recipient=item.recipient, body=item.body)
                    except Exception as exc:
                        error = exc
                async with SessionFactory() as session:
                    async with session.begin():
                        await service.complete_delivery(session, notification_id=item.id, error=error)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_forever())
