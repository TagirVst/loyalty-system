import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN_BARISTA = os.getenv("TELEGRAM_TOKEN_BARISTA")
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")

# Redis настройки для FSM storage
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB_BARISTA", 1))  # База 1 для бота бариста
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
