from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from redis.exceptions import RedisError
from fastapi.middleware.cors import CORSMiddleware
from app.core.monitoring import init_sentry, MetricsMiddleware, router as monitoring_router

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_handlers import (
    app_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    integrity_error_handler,
    redis_exception_handler,
    generic_exception_handler,
)
from app.core.logging_config import configure_logging
from app.api.v1.auth import router as auth_router
from app.api.v1 import products, cart, order, address, users, admin, webhooks, inventory, ws
from app.api.v1 import coupon

configure_logging()

from dotenv import load_dotenv
load_dotenv()

import os
import sentry_sdk
from fastapi import FastAPI

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=1.0,
)
app = FastAPI(title=settings.PROJECT_NAME)
init_sentry()
app.add_middleware(MetricsMiddleware)

import sentry_sdk
from sentry_sdk import metrics

sentry_sdk.init(
  dsn="https://20687881acf4d141ccff665ecb426a3b@o4511722837377024.ingest.us.sentry.io/4511722848911360",
)

metrics.count("checkout.failed", 1)
metrics.gauge("queue.depth", 42)
metrics.distribution("cart.amount_usd", 187.5)

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://192.168.1.37:3001"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Register Global Exception Handlers ====================
# Order matters: Specific pehle, Generic baad mein
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(RedisError, redis_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)  # Safety net, LAST

# ==================== Routers ====================
app.include_router(auth_router)
app.include_router(products.router, prefix="/api/v1/products", tags=["Catalog"])
app.include_router(cart.router, prefix="/api/v1/cart", tags=["Cart"])
app.include_router(order.router, prefix="/api/v1/orders", tags=["Orders"])
app.include_router(address.router, prefix="/api/v1/addresses", tags=["Addresses"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(coupon.router, prefix="/api/v1", tags=["Coupons"])
app.include_router(inventory.router, prefix="/api/v1/admin/inventory", tags=["Inventory"])
app.include_router(ws.router, prefix="/api/v1/ws", tags=["WebSockets"])
app.include_router(monitoring_router)


import os
print("DSN:", os.getenv("SENTRY_DSN"))  # Should print your DSN, not None
@app.get("/")
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}


