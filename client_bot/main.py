import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
import redis.asyncio as redis
from common.messages import *
from client_bot.handlers import router
from client_bot.config import TELEGRAM_TOKEN_CLIENT, REDIS_URL

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
        
        # Создаем RedisStorage с TTL 2 часа
        storage = RedisStorage(redis_client, ttl_seconds=7200)
        
        bot = Bot(token=TELEGRAM_TOKEN_CLIENT, parse_mode="HTML")
        dp = Dispatcher(storage=storage)
        dp.include_router(router)
        
        logger.info("Client Bot started with Redis storage")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Failed to start client bot: {e}")
        raise
    finally:
        # Закрываем Redis соединение при завершении
        if 'redis_client' in locals():
            await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
