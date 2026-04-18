from datetime import datetime, timedelta, timezone
from typing import Any, Union, Tuple
from jose import jwt, JWTError
from app.core.config import settings
from passlib.context import CryptContext

# Argon2-only policy for all password hashes.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


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

    to_encode = {'exp': expire, 'sub': str(subject)}

    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except JWTError as e:
        raise RuntimeError(f"Error encoding JWT: {str(e)}")
