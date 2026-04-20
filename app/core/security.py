from datetime import datetime, timedelta, timezone
from typing import Any, Union, Tuple
from jose import jwt, JWTError
from app.core.config import settings
from passlib.context import CryptContext
import redis.asyncio as redis
from redis.exceptions import RedisError

# Argon2-only policy for all password hashes.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def verify_and_update_password(plain_password: str, hashed_password: str) -> Tuple[bool, Union[str, None]]:
    return pwd_context.verify_and_update(plain_password, hashed_password)


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:

    if not subject:
        raise ValueError("Subject must not be None or empty.")

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {'exp': expire, 'sub': str(subject), "type": "access"}
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def create_refresh_token(subject: Union[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {'exp': expire, 'sub': str(subject), 'type': 'refresh'}  # Fixed variable name
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def blacklist_token(token: str, expiry: int):
    if not token:
        raise ValueError("Token must not be empty.")
    if expiry <= 0:
        raise ValueError("Expiry time must be greater than zero.")
    try:
        await redis_client.setex(name=token, time=expiry, value='blacklisted')
    except RedisError as exc:
        raise RuntimeError("Redis blacklist write failed.") from exc


async def is_token_blacklisted(token: str) -> bool:
    if not token:
        raise ValueError("Token must not be empty.")
    try:
        res = await redis_client.get(token)
    except RedisError as exc:
        raise RuntimeError("Redis blacklist read failed.") from exc
    return res == 'blacklisted'


def get_token_ttl_seconds(token: str) -> int:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        raise JWTError("Invalid token expiry claim.")
    ttl = int(exp - datetime.now(timezone.utc).timestamp())
    if ttl <= 0:
        raise JWTError("Token already expired.")
    return ttl



def create_password_reset_token(email: str) -> str:

    expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode = {"exp": expire, "sub": email, "type": "password_reset"}

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)



def create_verification_token(email: str)-> str:
    expire = datetime.now(timezone.utc) + timedelta(hours = 24)

    to_encode = {"exp": expire, "sub": email, "type": "email_verification"}

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


