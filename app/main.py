from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from redis.exceptions import RedisError

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
from app.api.v1 import products, cart, order, address, users, admin, webhooks


from app.api.v1 import coupon

configure_logging()

app = FastAPI(title=settings.PROJECT_NAME)

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


@app.get("/")
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}


@app.get("/test-logging")
async def test_logging():
    return {"message": "Logging middleware is working."}