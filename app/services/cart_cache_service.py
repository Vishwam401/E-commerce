

import uuid
import logging
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

CART_KEY_PREFIX = "cart:"
CART_TTL = settings.CART_CACHE_TTL  # 604800s = 7 days

# Lua: atomic add/increment — prevents race between concurrent HGET+HSET
ADD_ITEM_SCRIPT = """
local current = redis.call('HGET', KEYS[1], ARGV[1])
if current then
    local new_qty = tonumber(current) + tonumber(ARGV[2])
    redis.call('HSET', KEYS[1], ARGV[1], new_qty)
else
    redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
end
redis.call('EXPIRE', KEYS[1], ARGV[3])
return redis.call('HGET', KEYS[1], ARGV[1])
"""

# Lua: atomic decrement-or-remove — returns -1 (not found), 0 (removed), >0 (new qty)
DECREASE_ITEM_SCRIPT = """
local current = redis.call('HGET', KEYS[1], ARGV[1])
if not current then
    return -1
end
local new_qty = tonumber(current) - 1
if new_qty <= 0 then
    redis.call('HDEL', KEYS[1], ARGV[1])
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return 0
else
    redis.call('HSET', KEYS[1], ARGV[1], new_qty)
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return new_qty
end
"""


def _cart_key(user_id: uuid.UUID) -> str:
    return f"{CART_KEY_PREFIX}{user_id}"


def _get_redis() -> Redis:
    # Lazy import to avoid circular deps — singleton, so cheap
    from app.core.security import redis_client
    return redis_client


# ── Cart Item Operations ──

async def get_cart_from_cache(user_id: uuid.UUID) -> Optional[dict[str, int]]:
    """HGETALL → {product_id: quantity} or None on miss/error."""
    redis = _get_redis()
    try:
        raw = await redis.hgetall(_cart_key(user_id))
        if not raw:
            return None
        return {pid: int(qty) for pid, qty in raw.items()}
    except RedisError as exc:
        logger.warning(f"[CART_CACHE] Read failed: user={user_id}: {exc}")
        return None


async def add_item_to_cache(
    user_id: uuid.UUID, product_id: uuid.UUID, quantity: int
) -> Optional[int]:
    """Atomic add via Lua. Returns new total qty or None on error."""
    redis = _get_redis()
    try:
        result = await redis.eval(
            ADD_ITEM_SCRIPT, 1,
            _cart_key(user_id), str(product_id), str(quantity), str(CART_TTL),
        )
        return int(result) if result is not None else None
    except RedisError as exc:
        logger.warning(f"[CART_CACHE] Add failed: user={user_id}, product={product_id}: {exc}")
        return None


async def set_item_quantity(
    user_id: uuid.UUID, product_id: uuid.UUID, quantity: int
) -> bool:
    """HSET absolute qty (idempotent). For PUT endpoint."""
    redis = _get_redis()
    try:
        cart_key = _cart_key(user_id)
        await redis.hset(cart_key, str(product_id), str(quantity))
        await redis.expire(cart_key, CART_TTL)
        return True
    except RedisError as exc:
        logger.warning(f"[CART_CACHE] Set qty failed: user={user_id}, product={product_id}: {exc}")
        return False


async def remove_item_from_cache(
    user_id: uuid.UUID, product_id: uuid.UUID
) -> bool:
    """HDEL single item (idempotent)."""
    redis = _get_redis()
    try:
        cart_key = _cart_key(user_id)
        await redis.hdel(cart_key, str(product_id))
        await redis.expire(cart_key, CART_TTL)
        return True
    except RedisError as exc:
        logger.warning(f"[CART_CACHE] Remove failed: user={user_id}, product={product_id}: {exc}")
        return False


async def decrease_item_in_cache(
    user_id: uuid.UUID, product_id: uuid.UUID
) -> Optional[int]:
    """Atomic decrement via Lua. Returns -1/0/>0 or None on error."""
    redis = _get_redis()
    try:
        result = await redis.eval(
            DECREASE_ITEM_SCRIPT, 1,
            _cart_key(user_id), str(product_id), str(CART_TTL),
        )
        return int(result) if result is not None else None
    except RedisError as exc:
        logger.warning(f"[CART_CACHE] Decrease failed: user={user_id}, product={product_id}: {exc}")
        return None


async def clear_cart_cache(user_id: uuid.UUID) -> bool:
    """DEL cart key (idempotent). Called on clear/checkout."""
    redis = _get_redis()
    try:
        await redis.delete(_cart_key(user_id))
        return True
    except RedisError as exc:
        logger.warning(f"[CART_CACHE] Clear failed: user={user_id}: {exc}")
        return False


# ── Cache Population (DB → Redis) ──

async def populate_cache_from_db(
    user_id: uuid.UUID,
    items: dict[str, int],
) -> bool:
    """Bulk load cart items from DB into Redis via pipeline (single round-trip)."""
    if not items:
        return True

    redis = _get_redis()
    try:
        cart_key = _cart_key(user_id)

        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(cart_key)
            for product_id, qty in items.items():
                pipe.hset(cart_key, str(product_id), str(qty))
            pipe.expire(cart_key, CART_TTL)
            await pipe.execute()

        logger.info(f"[CART_CACHE] Populated: user={user_id}, items={len(items)}")
        return True
    except RedisError as exc:
        logger.warning(f"[CART_CACHE] Populate failed: user={user_id}: {exc}")
        return False
