from datetime import datetime, timedelta, timezone
from typing import Any, Union, Tuple
from jose import jwt, JWTError
from app.core.config import settings
from passlib.context import CryptContext
import redis.asyncio as redis
from redis.exceptions import RedisError
import logging

logger = logging.getLogger(__name__)

# Argon2-only policy for all password hashes.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    decode_responses=True,
)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def verify_and_update_password(plain_password: str, hashed_password: str) -> Tuple[bool, Union[str, None]]:
    return pwd_context.verify_and_update(plain_password, hashed_password)


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """
    🔐 Create access token with detailed logging

    Args:
        subject: Usually username or user ID
        expires_delta: Custom expiration time (defaults to settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    Returns:
        JWT token string
    """

    if not subject:
        logger.error("[TOKEN_CREATE] ❌ Subject is None or empty!")
        raise ValueError("Subject must not be None or empty.")

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
        logger.debug(f"[TOKEN_CREATE] Using custom expires_delta: {expires_delta}")
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        logger.debug(f"[TOKEN_CREATE] Using default ACCESS_TOKEN_EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")

    to_encode = {'exp': expire, 'sub': str(subject), "type": "access"}
    logger.debug(f"[TOKEN_CREATE] Token payload: exp={expire}, sub={subject}, type=access")
    logger.debug(f"[TOKEN_CREATE] Using ALGORITHM: {settings.ALGORITHM}")
    logger.debug(f"[TOKEN_CREATE] SECRET_KEY length: {len(settings.SECRET_KEY)}, first 15 chars: {settings.SECRET_KEY[:15]}")

    token = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    logger.info(f"[TOKEN_CREATE] ✅ Access token created for subject: {subject}")
    logger.debug(f"[TOKEN_CREATE] Token created, length: {len(token)}, first 40 chars: {token[:40]}")
    return token


def create_refresh_token(subject: Union[str, Any]) -> str:
    """🔐 Create refresh token valid for 7 days"""
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {'exp': expire, 'sub': str(subject), 'type': 'refresh'}
    logger.debug(f"[TOKEN_CREATE] Creating refresh token for subject: {subject}")
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def blacklist_token(token: str, expiry: int):
    """Add token to Redis blacklist (revoked tokens)"""
    if not token:
        logger.error("[TOKEN_BLACKLIST] ❌ Token is empty!")
        raise ValueError("Token must not be empty.")
    if expiry <= 0:
        logger.error("[TOKEN_BLACKLIST] ❌ Expiry time must be > 0")
        raise ValueError("Expiry time must be greater than zero.")
    try:
        await redis_client.setex(name=token, time=expiry, value='blacklisted')
        logger.info(f"[TOKEN_BLACKLIST] ✅ Token blacklisted for {expiry} seconds")
    except RedisError as exc:
        logger.error(f"[TOKEN_BLACKLIST] ❌ Redis write failed: {str(exc)}")
        raise RuntimeError("Redis blacklist write failed.") from exc


async def is_token_blacklisted(token: str) -> bool:
    """Check if token is in Redis blacklist"""
    if not token:
        logger.error("[TOKEN_CHECK_BLACKLIST] ❌ Token is empty!")
        raise ValueError("Token must not be empty.")
    try:
        res = await redis_client.get(token)
        is_blacklisted = res == 'blacklisted'
        if is_blacklisted:
            logger.warning("[TOKEN_CHECK_BLACKLIST] ⚠️ Token found in blacklist (revoked)")
        else:
            logger.debug("[TOKEN_CHECK_BLACKLIST] ✅ Token not in blacklist")
        return is_blacklisted
    except RedisError as exc:
        logger.error(f"[TOKEN_CHECK_BLACKLIST] ❌ Redis read failed: {str(exc)}")
        raise RuntimeError("Redis blacklist read failed.") from exc


def get_token_ttl_seconds(token: str) -> int:
    """Calculate remaining time-to-live for token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            logger.error("[TOKEN_TTL] ❌ Invalid exp claim type")
            raise JWTError("Invalid token expiry claim.")
        ttl = int(exp - datetime.now(timezone.utc).timestamp())
        if ttl <= 0:
            logger.warning("[TOKEN_TTL] ❌ Token already expired")
            raise JWTError("Token already expired.")
        logger.debug(f"[TOKEN_TTL] ✅ Token TTL: {ttl} seconds")
        return ttl
    except JWTError as e:
        logger.error(f"[TOKEN_TTL] ❌ JWT decode error: {str(e)}")
        raise


def create_password_reset_token(email: str) -> str:
    """Create password reset token valid for 15 minutes"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {"exp": expire, "sub": email, "type": "password_reset"}
    logger.debug(f"[TOKEN_CREATE] Creating password reset token for email: {email}")
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_verification_token(email: str)-> str:
    """Create email verification token valid for 24 hours"""
    expire = datetime.now(timezone.utc) + timedelta(hours = 24)
    to_encode = {"exp": expire, "sub": email, "type": "email_verification"}
    logger.debug(f"[TOKEN_CREATE] Creating email verification token for email: {email}")
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


