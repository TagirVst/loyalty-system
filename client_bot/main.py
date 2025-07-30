import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from common.messages import *
from client_bot.handlers import router
from client_bot.config import TELEGRAM_TOKEN_CLIENT

async def main():
    bot = Bot(token=TELEGRAM_TOKEN_CLIENT, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    print("Client Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
