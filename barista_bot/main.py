import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from common.messages import *
from barista_bot.handlers import router
from barista_bot.config import TELEGRAM_TOKEN_BARISTA

async def main():
    bot = Bot(token=TELEGRAM_TOKEN_BARISTA, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    print("Barista Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
