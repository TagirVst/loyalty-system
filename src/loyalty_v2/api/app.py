from fastapi import FastAPI

from loyalty_v2.api.admin_analytics_routes import router as admin_analytics_router
from loyalty_v2.api.admin_config_routes import router as admin_config_router
from loyalty_v2.api.admin_customer_routes import router as admin_customer_router
from loyalty_v2.api.admin_notification_routes import router as admin_notification_router
from loyalty_v2.api.admin_override_routes import router as admin_override_router
from loyalty_v2.api.admin_staff_routes import router as admin_staff_router
from loyalty_v2.api.customer_routes import router as customer_router
from loyalty_v2.api.engagement_routes import router as engagement_router
from loyalty_v2.api.integration_routes import router as integration_router
from loyalty_v2.api.secure_policy_routes import router as secure_policy_router
from loyalty_v2.api.secure_routes import router as secure_router
from loyalty_v2.api.system_routes import router as system_router
from loyalty_v2.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="2.0.0-dev")
app.include_router(system_router)
app.include_router(secure_router)
app.include_router(secure_policy_router)
app.include_router(admin_config_router)
app.include_router(admin_staff_router)
app.include_router(admin_customer_router)
app.include_router(admin_override_router)
app.include_router(admin_notification_router)
app.include_router(admin_analytics_router)
app.include_router(integration_router)
app.include_router(engagement_router)
app.include_router(customer_router)
