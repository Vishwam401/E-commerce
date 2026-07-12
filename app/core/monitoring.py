
from __future__ import annotations

import logging
import time

import sentry_sdk
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.security import redis_client
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Monitoring"])


# ── 1. SENTRY — error tracking ──
def init_sentry() -> None:
    dsn = getattr(settings, "SENTRY_DSN", None)
    if not dsn:
        logger.info("[SENTRY] DSN not set — error tracking disabled")
        return
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=getattr(settings, "ENVIRONMENT", "development"),
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logger.info("[SENTRY] Initialized")
    except Exception as exc:
        logger.error(f"[SENTRY] Init failed (galat DSN?): {exc}")


# ── 2. METRICS — simple in-memory counters ──
class _Metrics:
    def __init__(self) -> None:
        self.request_count = 0
        self.error_count = 0
        self.total_latency = 0.0  # seconds

    def record(self, latency: float, status_code: int) -> None:
        self.request_count += 1
        self.total_latency += latency
        if status_code >= 500:
            self.error_count += 1


metrics = _Metrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Har request ka latency + status record karta hai."""

    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            metrics.record(time.perf_counter() - start, 500)
            raise
        metrics.record(time.perf_counter() - start, response.status_code)
        return response


# ── 3. ENDPOINTS ──
@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks: dict[str, str] = {}
    healthy = True

    # DB ping
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.error(f"[HEALTH] DB down: {exc}")
        checks["database"] = "down"
        healthy = False

    # Redis ping
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error(f"[HEALTH] Redis down: {exc}")
        checks["redis"] = "down"
        healthy = False

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "healthy" if healthy else "unhealthy", "checks": checks},
    )


@router.get("/metrics")
async def get_metrics():
    rc = metrics.request_count
    avg_latency_ms = round((metrics.total_latency / rc) * 1000, 2) if rc else 0.0
    error_rate = round(metrics.error_count / rc, 4) if rc else 0.0
    return {
        "request_count": rc,
        "error_count": metrics.error_count,
        "avg_latency_ms": avg_latency_ms,
        "error_rate": error_rate,
    }