
import json
import logging
import uuid
from typing import Optional, Dict, Any

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.security import redis_client

logger = logging.getLogger(__name__)

PRODUCT_KEY_PREFIX = "product:"
PRODUCT_TTL = settings.PRODUCT_CACHE_TTL


def _product_key(product_id: uuid.UUID | str) -> str:
    return f"{PRODUCT_KEY_PREFIX}{product_id}"


async def get_product_from_cache(product_id: uuid.UUID | str) -> Optional[Dict[str, Any]]:
    """Get a product from Redis. Returns dict if found, None on miss/error."""
    try:
        raw_data = await redis_client.get(_product_key(product_id))
        if not raw_data:
            return None
        return json.loads(raw_data)
    except RedisError as exc:
        logger.warning(f"[PRODUCT_CACHE] Read failed: product={product_id}: {exc}")
        return None
    except json.JSONDecodeError:
        logger.warning(f"[PRODUCT_CACHE] JSON decode failed for product={product_id}")
        return None


async def set_product_in_cache(product_id: uuid.UUID | str, product_data: Dict[str, Any]) -> None:
    """Store a product in Redis with TTL."""
    try:
        json_data = json.dumps(product_data)
        await redis_client.setex(
            name=_product_key(product_id),
            time=PRODUCT_TTL,
            value=json_data
        )
    except RedisError as exc:
        logger.warning(f"[PRODUCT_CACHE] Write failed: product={product_id}: {exc}")


async def invalidate_product_cache(product_id: uuid.UUID | str) -> None:
    """Delete a product from Redis."""
    try:
        await redis_client.delete(_product_key(product_id))
    except RedisError as exc:
        logger.warning(f"[PRODUCT_CACHE] Invalidate failed: product={product_id}: {exc}")

# ── Product List Caching (Cache-Aside for listing pages) ─

LIST_KEY_PREFIX = "products:list:"
LIST_VERSION_KEY = "products:list:version"


async def _get_list_version() -> int:
    """
    Current version number. Defaults to 0 if not set yet — this matches
    Redis INCR semantics on a missing key (0 -> 1), so the very first
    invalidation always produces a version different from the default
    read version. Without this, the first invalidation would be a silent
    no-op (both would resolve to 1).
    """
    try:
        version = await redis_client.get(LIST_VERSION_KEY)
        return int(version) if version else 0
    except RedisError as exc:
        logger.warning(f"[PRODUCT_CACHE] Version read failed: {exc}")
        return 0


def _list_key(version: int, skip: int, limit: int) -> str:
    return f"{LIST_KEY_PREFIX}v{version}:skip={skip}:limit={limit}"


async def get_product_list_from_cache(skip: int, limit: int) -> Optional[list]:
    """Get cached product list page. Returns list if found, None on miss/error."""
    try:
        version = await _get_list_version()
        key = _list_key(version, skip, limit)
        raw_data = await redis_client.get(key)
        if not raw_data:
            return None
        return json.loads(raw_data)
    except RedisError as exc:
        logger.warning(f"[PRODUCT_CACHE] List read failed: skip={skip}, limit={limit}: {exc}")
        return None
    except json.JSONDecodeError:
        logger.warning(f"[PRODUCT_CACHE] List JSON decode failed: skip={skip}, limit={limit}")
        return None


async def set_product_list_in_cache(skip: int, limit: int, products_data: list) -> None:
    """Store a product list page in Redis with TTL."""
    try:
        version = await _get_list_version()
        key = _list_key(version, skip, limit)
        json_data = json.dumps(products_data)
        await redis_client.setex(name=key, time=PRODUCT_TTL, value=json_data)
    except RedisError as exc:
        logger.warning(f"[PRODUCT_CACHE] List write failed: skip={skip}, limit={limit}: {exc}")


async def invalidate_product_list_cache() -> None:
    """
    Invalidate all list cache pages by bumping the version number.
    Old keys are left alone — they expire naturally via TTL.
    """
    try:
        await redis_client.incr(LIST_VERSION_KEY)
    except RedisError as exc:
        logger.warning(f"[PRODUCT_CACHE] List invalidate failed: {exc}")
