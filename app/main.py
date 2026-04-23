from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.auth import router as auth_router
from app.api.v1 import products, cart
import logging
import logging.config
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "stream": "ext://sys.stdout"
        }
    },
    "loggers": {
        "app": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False
        },
        "app.core.security": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False
        },
        "app.api.dependencies": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False
        },
        "app.api.v1.auth": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False
        }
    }
}

logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(auth_router)
app.include_router(products.router, prefix="/api/v1/products", tags=["Catalog"])

app.include_router(cart.router, prefix="/api/v1/cart", tags=["Cart"])
@app.get("/")
async def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME}

@app.get("/test-logging")
async def test_logging():
    return {"message": "Logging middleware is working."}


