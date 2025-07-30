import os
from dotenv import load_dotenv
import sys

load_dotenv()

class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEBUG: bool = ENV == "dev"
    
    # Database settings с проверкой обязательных переменных
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
    
    # Проверяем обязательные переменные базы данных
    if not all([POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]):
        print("ERROR: Missing required database environment variables (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)")
        sys.exit(1)
    
    DATABASE_URL: str = (
        f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    # Security settings с проверкой обязательных переменных
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ADMIN_LOGIN: str = os.getenv("ADMIN_LOGIN")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD")
    
    # Проверяем обязательные переменные безопасности
    if not all([SECRET_KEY, ADMIN_LOGIN, ADMIN_PASSWORD]):
        print("ERROR: Missing required security environment variables (SECRET_KEY, ADMIN_LOGIN, ADMIN_PASSWORD)")
        sys.exit(1)
    
    # Проверяем минимальную длину SECRET_KEY
    if len(SECRET_KEY) < 32:
        print("ERROR: SECRET_KEY must be at least 32 characters long")
        sys.exit(1)

settings = Settings()
