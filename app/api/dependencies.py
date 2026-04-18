from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import User
from app.core.security import is_token_blacklisted
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
):
    # 1. Redis Check: Kya user logout kar chuka hai?
    if await is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked (logged out)."
        )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email_value = payload.get("sub")
        if not isinstance(email_value, str) or not email_value:
            raise HTTPException(status_code=401, detail="Invalid token payload.")
        email = email_value
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials.")

    # 2. Database Check
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user.")

    return user