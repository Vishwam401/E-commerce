import logging
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import is_rate_limited
from app.core.security import (
    blacklist_token,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_verification_token,
    get_password_hash,
    get_token_ttl_seconds,
    redis_client,
    verify_and_update_password,
    is_token_blacklisted,
)
from app.core.exceptions import (
    ConflictError,
    RateLimitError,
    AuthenticationError,
    AccountInactiveError,
    TokenCompromisedError,
    InvalidTokenError,
    NotFoundError,
)
from app.db.models import User
from app.schemas.user import PasswordResetCheck, PasswordResetConfirm, UserCreate
from app.utils.email import send_verification_email

logger = logging.getLogger(__name__)


async def register_user_service(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> User:
    query = select(User).where(func.lower(User.email) == user_in.email.lower())
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.info("[REGISTER] Email already exists")
        raise ConflictError("User with this email already exists.")

    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email.lower(),
        username=user_in.username,
        hashed_password=hashed_password,
        is_active=False,
        full_name=user_in.full_name,
        phone_number=user_in.phone_number,
    )

    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)

        token = create_verification_token(new_user.email)
        background_tasks.add_task(send_verification_email, new_user.email, token)
        return new_user
    except IntegrityError:
        await db.rollback()
        logger.info("[REGISTER] Duplicate username/email")
        raise ConflictError("Username or email already exists.")


async def resend_verification_service(
    email: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> dict:
    query = select(User).where(func.lower(User.email) == email.lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        return {"detail": "If email exists, verification link sent."}

    if user.is_active:
        return {"detail": "Account already verified"}

    cooldown_key = f"email_cooldown:{email.lower()}"
    try:
        if await redis_client.get(cooldown_key):
            raise RateLimitError("Please wait 2 minutes before requesting another email.")
        await redis_client.setex(cooldown_key, 120, "locked")
    except RedisError:
        pass

    token = create_verification_token(user.email)
    background_tasks.add_task(send_verification_email, user.email, token)
    return {"detail": "If email exists, verification link sent."}


async def login_service(
    request: Request,
    db: AsyncSession,
    form_data: OAuth2PasswordRequestForm,
) -> dict:
    logger.info("[LOGIN] Attempt")

    client_ip = request.client.host if request.client else "unknown"
    ip_rate_key = f"rate_limit:login:ip:{client_ip}"
    username_attempt = form_data.username.lower()
    user_rate_key = f"rate_limit:login:user:{username_attempt}"

    try:
        if await is_rate_limited(ip_rate_key, limit=5, window=60, redis_client=redis_client):
            logger.warning("[LOGIN] IP Rate limit exceeded")
            raise RateLimitError("Too many login attempts from your IP. Please try again later.")

        if await is_rate_limited(user_rate_key, limit=5, window=60, redis_client=redis_client):
            logger.warning(f"[LOGIN] User account brute-force detected for {username_attempt}")
            raise RateLimitError("Account temporarily locked due to too many failed attempts.")
    except RedisError:
        logger.warning("[LOGIN] Rate limiter unavailable (Redis error); continuing")

    query = select(User).where(func.lower(User.email) == form_data.username.lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("Incorrect email or password")

    is_valid_password, new_hash = verify_and_update_password(
        form_data.password, user.hashed_password
    )
    if not is_valid_password:
        raise AuthenticationError("Incorrect email or password")

    if not user.is_active:
        raise AccountInactiveError()

    if new_hash:
        user.hashed_password = new_hash
        await db.commit()

    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def logout_service(token: str) -> dict:
    try:
        ttl_seconds = get_token_ttl_seconds(token)
    except JWTError:
        raise InvalidTokenError("Invalid or expired token")

    await blacklist_token(token, expiry=ttl_seconds)
    return {"detail": "Successfully logged out"}


async def refresh_token_service(refresh_token: str) -> dict:
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type = payload.get("type")
        if token_type != "refresh":
            raise InvalidTokenError("Invalid refresh token")

        subject = payload.get("sub")
        if not subject:
            raise InvalidTokenError("Invalid refresh token")

        if await is_token_blacklisted(refresh_token):
            logger.critical(f"[TOKEN THEFT] Blacklisted refresh token used by {subject}")
            raise TokenCompromisedError()

    except JWTError:
        raise InvalidTokenError("Refresh token expired or invalid")

    ttl = get_token_ttl_seconds(refresh_token)
    await blacklist_token(refresh_token, expiry=ttl)

    new_access_token = create_access_token(subject=subject)
    new_refresh_token = create_refresh_token(subject=subject)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


async def forgot_password_service(
    data: PasswordResetCheck,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> dict:
    result = await db.execute(
        select(User).where(func.lower(User.email) == data.email.lower())
    )
    user = result.scalar_one_or_none()

    if user:
        token = create_password_reset_token(data.email)
        background_tasks.add_task(send_verification_email, user.email, token)

    return {"detail": "If this email exists, a password reset link has been sent."}


async def reset_password_service(
    data: PasswordResetConfirm,
    db: AsyncSession,
) -> dict:
    if await is_token_blacklisted(data.token):
        raise InvalidTokenError("This reset link has already been used or expired.")

    try:
        payload = jwt.decode(data.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset":
            raise InvalidTokenError("Invalid token type")

        token_email = payload.get("sub")
        if not isinstance(token_email, str) or not token_email:
            raise InvalidTokenError("Invalid token payload")
    except JWTError:
        raise InvalidTokenError("Token expired or invalid")

    if token_email.lower() != data.email.lower():
        raise InvalidTokenError("Email and token do not match")

    result = await db.execute(
        select(User).where(func.lower(User.email) == data.email.lower())
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")

    user.hashed_password = get_password_hash(data.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()

    ttl = get_token_ttl_seconds(data.token)
    await blacklist_token(data.token, expiry=ttl)

    return {
        "detail": "Password successfully reset! All other devices have been logged out."
    }


async def verify_email_service(token: str, db: AsyncSession) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "email_verification":
            raise InvalidTokenError("Invalid token type")
        email = payload.get("sub")
    except JWTError:
        raise InvalidTokenError("Link is expired or invalid")

    result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")

    if user.is_active:
        return {"detail": "Account already verified."}

    user.is_active = True
    await db.commit()

    ttl = get_token_ttl_seconds(token)
    await blacklist_token(token, expiry=ttl)

    return {"detail": "Congratulations! Your account is verified."}

