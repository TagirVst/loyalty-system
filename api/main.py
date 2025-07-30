from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.config import settings

from api.routes import users, orders, codes, feedback, gifts, analytics, notifications

# Создаем limiter для rate limiting
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Loyalty System API",
    description="API для системы лояльности кофейни. Swagger/OpenAPI с примерами.",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,  # Отключаем docs в продакшене
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Добавляем rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS настройки в зависимости от окружения
cors_origins = ["*"] if settings.DEBUG else [
    "http://localhost:3000",
    "http://localhost:8080", 
    "https://yourdomain.com"  # Замените на ваш домен
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Роуты
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(codes.router, prefix="/codes", tags=["codes"])
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
app.include_router(gifts.router, prefix="/gifts", tags=["gifts"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
