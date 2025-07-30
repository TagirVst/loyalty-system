import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
import redis.asyncio as redis
from common.messages import *
from barista_bot.handlers import router
from barista_bot.config import TELEGRAM_TOKEN_BARISTA, REDIS_URL

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    try:
        # Создаем Redis клиент для FSM storage
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        
        # Проверяем подключение к Redis
        await redis_client.ping()
        logger.info("Successfully connected to Redis")
        
        # Создаем RedisStorage с TTL 4 часа (у баристы смены дольше)
        storage = RedisStorage(redis_client, ttl_seconds=14400)
        
        bot = Bot(token=TELEGRAM_TOKEN_BARISTA, parse_mode="HTML")
        dp = Dispatcher(storage=storage)
        dp.include_router(router)
        
        logger.info("Barista Bot started with Redis storage")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Failed to start barista bot: {e}")
        raise
    finally:
        # Закрываем Redis соединение при завершении
        if 'redis_client' in locals():
            await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
