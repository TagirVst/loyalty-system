from fastapi import FastAPI

from loyalty_v2.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name, version="2.0.0-dev")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "loyalty-v2"}
