import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEBUG: bool = ENV == "dev"
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "loyalty_db")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "loyalty_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "loyaltypass")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
    DATABASE_URL: str = (
        f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ADMIN_LOGIN: str = os.getenv("ADMIN_LOGIN", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

settings = Settings()
