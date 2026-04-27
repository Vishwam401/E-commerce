from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.auth import router as auth_router
from app.api.v1 import products, cart, order, address, admin
from app.core.logging_config import configure_logging


configure_logging()

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(auth_router)
app.include_router(products.router, prefix="/api/v1/products", tags=["Catalog"])

app.include_router(cart.router, prefix="/api/v1/cart", tags=["Cart"])

app.include_router(order.router, prefix="/api/v1/orders", tags=["Orders"])

app.include_router(address.router, prefix="/api/v1/addresses", tags=["Addresses"])

app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

@app.get("/")
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}

@app.get("/test-logging")
async def test_logging():
    return {"message": "Logging middleware is working."}