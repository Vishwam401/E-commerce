from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import cast
import logging
from datetime import datetime, timezone

from app.db.session import get_db
from app.db.models import User
from app.core.security import is_token_blacklisted
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
logger = logging.getLogger(__name__)


def _unauthorized(detail: str = "Invalid or expired credentials.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _forbidden(detail: str = "Not enough permissions.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _service_unavailable(detail: str = "Auth service temporarily unavailable.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    AUTHENTICATION FLOW DEBUG:
    1. Check token blacklist status
    2. Decode JWT payload
    3. Verify token type (access)
    4. Extract username from token
    5. Lookup user in database
    6. Verify user.is_active status
    """

    logger.info(f"[AUTH_FLOW] Starting authentication with token (first 20 chars): {token[:20]}...")

    # ===== STEP 1: CHECK TOKEN BLACKLIST =====
    try:
        is_blacklisted = await is_token_blacklisted(token)
        if is_blacklisted:
            logger.warning(f"[AUTH_FLOW] Token is blacklisted (revoked). Rejecting request.")
            raise _unauthorized("Token revoked. Please login again.")
        logger.debug("[AUTH_FLOW] ✅ Token not blacklisted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AUTH_FLOW] ❌ Redis/blacklist error: {str(e)}")
        raise _service_unavailable()

    # ===== STEP 2: DECODE JWT TOKEN =====
    try:
        logger.debug("[AUTH_FLOW] Decoding token (SECRET_KEY redacted)")
        logger.debug(f"[AUTH_FLOW] Token length: {len(token)}, first 30 chars: {token[:30]}")
        logger.debug(f"[AUTH_FLOW] Decoding with ALGORITHM: {settings.ALGORITHM}")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        logger.debug(f"[AUTH_FLOW] ✅ Token decoded successfully. Payload keys: {payload.keys()}")
        logger.debug(f"[AUTH_FLOW] Payload: {payload}")

        # ===== STEP 3: VERIFY TOKEN TYPE =====
        token_type = payload.get("type")
        logger.debug(f"[AUTH_FLOW] Token type: {token_type}")
        if token_type != "access":
            logger.warning(f"[AUTH_FLOW] ❌ Wrong token type. Expected 'access', got '{token_type}'")
            raise _unauthorized("Access token required.")

        # ===== STEP 4: EXTRACT USERNAME =====
        subject = payload.get("sub")
        logger.debug(f"[AUTH_FLOW] Extracted subject (username): {subject}")
        if not isinstance(subject, str) or not subject:
            logger.warning(f"[AUTH_FLOW] ❌ Invalid subject in token: {subject}")
            raise _unauthorized()

        # ===== STEP 5: CHECK TOKEN EXPIRY =====
        exp = payload.get("exp")
        if exp and isinstance(exp, (int, float)):
            current_time = datetime.now(timezone.utc).timestamp()
            time_remaining = float(exp) - current_time
            logger.debug(f"[AUTH_FLOW] Token expiry (exp): {exp}, Current time: {current_time}, Time remaining: {time_remaining:.2f}s")
            if time_remaining <= 0:
                logger.warning(f"[AUTH_FLOW] ❌ Token has expired. Exp: {exp}, Current: {current_time}")
                raise _unauthorized("Token has expired.")

    except JWTError as e:
        logger.error(f"[AUTH_FLOW] ❌ JWT decode error: {str(e)}")
        raise _unauthorized()

    # ===== STEP 6: LOOKUP USER IN DATABASE =====
    logger.debug(f"[AUTH_FLOW] Looking up user with username: '{subject}'")
    result = await db.execute(select(User).where(User.username == subject))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"[AUTH_FLOW] ❌ User not found in database for username: '{subject}'")
        raise _unauthorized("User not found.")

    logger.debug(f"[AUTH_FLOW] ✅ User found: ID={user.id}, Username={user.username}")

    # ===== STEP 7: VERIFY USER IS ACTIVE =====
    logger.debug(f"[AUTH_FLOW] Checking is_active flag for user '{subject}': {user.is_active}")
    if not user.is_active:
        logger.warning(f"[AUTH_FLOW] ❌ User account not verified. is_active=False for user: '{subject}'")
        logger.warning(f"[AUTH_FLOW]    → User must verify email first or admin must activate account")
        raise _unauthorized("Account is not active. Please verify your email.")

    logger.info(f"[AUTH_FLOW] ✅ Authentication successful for user: '{subject}'")
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
            raise _forbidden("Required role not found.")
        return current_user

    return _role_checker


async def get_current_admin_user(
    current_user: User = Depends(require_roles("admin")),
) -> User:
    return current_user
