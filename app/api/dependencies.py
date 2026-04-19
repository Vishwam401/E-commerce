from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import cast

from app.db.session import get_db
from app.db.models import User
from app.core.security import is_token_blacklisted
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


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
    try:
        if await is_token_blacklisted(token):
            raise _unauthorized("Token revoked. Please login again.")
    except HTTPException:
        raise
    except Exception:
        raise _service_unavailable()

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        token_type = payload.get("type")
        if token_type != "access":
            raise _unauthorized("Access token required.")

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise _unauthorized()
    except JWTError:
        raise _unauthorized()

    result = await db.execute(select(User).where(User.username == subject))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise _unauthorized()

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
