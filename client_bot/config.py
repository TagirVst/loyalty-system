import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN_CLIENT = os.getenv("TELEGRAM_TOKEN_CLIENT")
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
