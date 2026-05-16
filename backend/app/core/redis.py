from typing import Any


async def is_rate_limited(key: str, limit: int, window: int, redis_client: Any) -> bool:
    """
    Return True when request should be blocked, else False.

    key: Unique key (e.g., rate_limit:login:IP_ADDRESS)
    limit: Max allowed requests in the time window
    window: TTL window in seconds (e.g., 60 for 1 minute)
    """
    current = await redis_client.get(key)

    # Redis may return str/bytes/int depending on client settings.
    if current is not None and int(current) >= limit:
        return True

    if current is None:
        # First request in the window starts counter with expiry.
        await redis_client.setex(key, window, 1)
    else:
        await redis_client.incr(key)

    return False
