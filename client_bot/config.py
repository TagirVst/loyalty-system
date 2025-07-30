import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN_CLIENT = os.getenv("TELEGRAM_TOKEN_CLIENT")
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")

# Redis настройки для FSM storage
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB_CLIENT", 0))  # База 0 для клиентского бота
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
