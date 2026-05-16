from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import cast

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.security import is_token_blacklisted
from app.core.exceptions import (
    AuthenticationError,
    UnauthorizedError,
    ForbiddenError,
    ServiceUnavailableError,
    SessionInvalidatedError,
    AccountInactiveError,
    TokenCompromisedError,
)
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Auth flow:
      1. Reject blacklisted tokens
      2. Decode JWT and validate token type=access
      3. Validate subject and expiry
      4. Lookup user and ensure is_active
    """

    # Step 1: token blacklist check (Redis)
    try:
        if await is_token_blacklisted(token):
            logger.warning("[AUTH] Token is blacklisted")
            raise AuthenticationError("Token revoked. Please login again.")
    except AuthenticationError:
        raise
    except Exception as exc:
        logger.error(f"[AUTH] Blacklist check failed: {str(exc)}")
        raise ServiceUnavailableError("Auth service temporarily unavailable.")

    # Step 2: decode JWT + validate claims
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        token_type = payload.get("type")
        if token_type != "access":
            logger.info(f"[AUTH] Wrong token type: {token_type}")
            raise AuthenticationError("Access token required.")

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("Invalid token structure")

        iat = payload.get("iat")
        exp = payload.get("exp")
        if exp and isinstance(exp, (int, float)):
            if float(exp) - datetime.now(timezone.utc).timestamp() <= 0:
                raise AuthenticationError("Token has expired.")
    except JWTError as exc:
        logger.info(f"[AUTH] JWT decode failed: {str(exc)}")
        raise AuthenticationError("Invalid or expired token.")

    # Step 3: user lookup + active check
    try:
        user_uuid = uuid.UUID(subject)
    except ValueError:
        logger.error(f"[AUTH] Subject is not a valid UUID: {subject}")
        raise AuthenticationError("Invalid token structure")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("User not found.")

    # Session invalidation check
    if iat and user.password_changed_at:
        token_issued_at = datetime.fromtimestamp(iat, timezone.utc)
        if token_issued_at < user.password_changed_at:
            logger.warning(f"[AUTH] Invalidated session accessed by {user.id}")
            raise SessionInvalidatedError()

    if not user.is_active:
        raise AccountInactiveError()

    return cast(User, user)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


def require_roles(*roles: str):
    required = {r.lower() for r in roles}

    async def _role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        user_roles = {"admin"} if current_user.is_admin else {"user"}
        if not (required & user_roles):
            raise ForbiddenError("Required role not found.")
        return current_user

    return _role_checker


async def get_current_admin_user(
    current_user: User = Depends(require_roles("admin")),
) -> User:
    return current_user