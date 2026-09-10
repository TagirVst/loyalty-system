from fastapi import FastAPI

from loyalty_v2.api.customer_policy_routes import router as customer_policy_router
from loyalty_v2.api.routes import router
from loyalty_v2.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name, version="2.0.0-dev")
app.include_router(router)
app.include_router(customer_policy_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "loyalty-v2"}
