"""
Global Exception Handlers for FastAPI

Logic: FastAPI mein jab bhi koi exception raise hoti hai,
yeh handlers usko pakad ke JSON response bana dete hain.
Registration: app/main.py mein add_exception_handler() se hoti hai.
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from redis.exceptions import RedisError

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException):
    """
    Sab custom exceptions (AppException ke child) yahan aayengi.
    Unka status_code aur message automatically JSON mein convert ho jayega.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "path": str(request.url.path)
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Pydantic schema validation fail hone pe (e.g. missing field, wrong type)
    """
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "details": exc.errors()
        }
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """
    Database query fail hone pe.
    User ko generic message do, developer ko logs mein detail milegi.
    """
    logger.error(f"Database error at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "DATABASE_ERROR",
            "message": "Internal database error"
        }
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    """
    Unique constraint violate hone pe (duplicate email, etc.)
    """
    logger.warning(f"Integrity error at {request.url.path}: {exc}")
    return JSONResponse(
        status_code=409,
        content={
            "error_code": "INTEGRITY_ERROR",
            "message": "Resource already exists or constraint violated"
        }
    )


async def redis_exception_handler(request: Request, exc: RedisError):
    """
    Redis down hone pe
    """
    logger.error(f"Redis error at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={
            "error_code": "CACHE_SERVICE_ERROR",
            "message": "Cache service temporarily unavailable"
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """
    Safety net: Koi bhi exception jo upar ke handlers se nahi pakdi gayi.
    Production mein user ko generic message, logs mein full traceback.
    """
    logger.critical(f"Unhandled exception at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred"
        }
    )