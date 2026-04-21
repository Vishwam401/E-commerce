from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.auth import router as auth_router
from app.api.v1 import products
import logging

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(auth_router)
app.include_router(products.router, prefix="/api/v1/products", tags=["Catalog"])


@app.get("/")
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}

@app.get("/test-logging")
async def test_logging():
    return {"message": "Logging middleware is working."}


