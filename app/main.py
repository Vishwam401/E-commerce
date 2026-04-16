from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

@app.get("/")
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}