from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.auth import router as auth_router
import logging

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(auth_router)


@app.get("/")
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}

@app.get("/test-logging")
async def test_logging():
    return {"message": "Logging middleware is working."}
