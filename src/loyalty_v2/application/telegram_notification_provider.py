from __future__ import annotations

from aiogram import Bot


class TelegramNotificationProvider:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send(self, *, recipient: str, body: str) -> None:
        await self.bot.send_message(chat_id=int(recipient), text=body)
