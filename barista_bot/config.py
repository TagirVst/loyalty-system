import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN_BARISTA = os.getenv("TELEGRAM_TOKEN_BARISTA")
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
