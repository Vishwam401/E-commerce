import logging
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_roles
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
from app.db.models import User
from app.db.session import get_db
from app.schemas.user import PasswordResetCheck, PasswordResetConfirm, UserCreate, UserOut
from app.utils.email import send_verification_email

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    query = select(User).where(func.lower(User.email) == user_in.email.lower())
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.info("[REGISTER] Email already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists.",
        )

    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email.lower(),
        username=user_in.username,
        hashed_password=hashed_password,
        is_active=False,
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists.",
        )

@router.post("/resend-verification")
async def resend_verification(
        email: str,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db)
):
    query = select(User).where(func.lower(User.email) == email.lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # Enum attack rokne ke liye generic response
    if not user:
        return {"detail": "If email exists, verification link sent,"}

    if user.is_active:
        return{"detail": "Account already verified"}

    # Rate limit check
    cooldown_key = f"email_cooldown:{email.lower()}"
    try:
        if await redis_client.get(cooldown_key):
            raise HTTPException(status_code=429, detail="Please wait 2 minutes before requesting another email.")
        await redis_client.setex(cooldown_key, 120, "locked")
    except RedisError:
        pass

    token = create_verification_token(user.email)
    background_tasks.add_task(send_verification_email, user.email, token)
    return {"detail": "If email exists, verification link sent"}


@router.post("/login")
async def login(
        request: Request,
        db: AsyncSession = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends(),
):
    logger.info("[LOGIN] Attempt")

    # Rate-limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    ip_rate_key = f"rate_limit:login:ip:{client_ip}"

    # === CHANGED/ADDED CODE START ===
    # Username rate limiting to prevent distributed brute-force attacks via Proxies
    username_attempt = form_data.username.lower()
    user_rate_key = f"rate_limit:login:user:{username_attempt}"

    try:
        if await is_rate_limited(ip_rate_key, limit=5, window=60, redis_client=redis_client):
            logger.warning("[LOGIN] IP Rate limit exceeded")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts from your IP. Please try again later.",
                headers={"Retry-After": "60"}
            )

        if await is_rate_limited(user_rate_key, limit=5, window=60, redis_client=redis_client):
            logger.warning(f"[LOGIN] User account brute-force detected for {username_attempt}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked due to too many failed attempts.",
                headers={"Retry-After": "60"}
            )
    except RedisError:
        logger.warning("[LOGIN] Rate limiter unavailable (Redis error); continuing")
    # === CHANGED/ADDED CODE END ===

    query = select(User).where(func.lower(User.email) == form_data.username.lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_valid_password, new_hash = verify_and_update_password(form_data.password, user.hashed_password)
    if not is_valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in.",
        )

    if new_hash:
        user.hashed_password = new_hash
        await db.commit()

    # === CHANGED/ADDED CODE START ===
    # Using user.id (UUID) instead of username for better performance & security
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    # === CHANGED/ADDED CODE END ===

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    try:
        ttl_seconds = get_token_ttl_seconds(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    await blacklist_token(token, expiry=ttl_seconds)

    return {"detail": "Successfully logged out"}


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        subject = payload.get("sub")
        if not subject:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        # === CHANGED/ADDED CODE START ===
        # THEFT DETECTION
        if await is_token_blacklisted(refresh_token):
            logger.critical(f"[TOKEN THEFT] Attempt to use blacklisted refresh token by {subject}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Token compromised. Please login again.")

    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or invalid")

    # REFRESH TOKEN ROTATION
    ttl = get_token_ttl_seconds(refresh_token)
    await blacklist_token(refresh_token, expiry=ttl)

    new_access_token = create_access_token(subject=subject)
    new_refresh_token = create_refresh_token(subject=subject)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }
    # === CHANGED/ADDED CODE END ===


@router.post("/admin-only")
async def admin_only_action(current_user: User = Depends(require_roles("admin"))):
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(data: PasswordResetCheck, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(func.lower(User.email) == data.email.lower()))
    user = result.scalar_one_or_none()

    if user:
        _ = create_password_reset_token(data.email)

    return {"detail": "If this email exists, a reset token has been generated (simulated)."}


@router.post("/reset-password")
async def reset_password(data: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    # === CHANGED/ADDED CODE START ===
    # Single-use reset token check
    if await is_token_blacklisted(data.token):
        raise HTTPException(status_code=400, detail="This reset link has already been used or expired.")
    # === CHANGED/ADDED CODE END ===

    try:
        payload = jwt.decode(data.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset":
            raise HTTPException(status_code=400, detail="Invalid token type")

        token_email = payload.get("sub")
        if not isinstance(token_email, str) or not token_email:
            raise HTTPException(status_code=400, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=400, detail="Token expired or invalid")

    if token_email.lower() != data.email.lower():
        raise HTTPException(status_code=400, detail="Email and token do not match")

    result = await db.execute(select(User).where(func.lower(User.email) == data.email.lower()))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    user.hashed_password = get_password_hash(data.new_password)

    # === CHANGED/ADDED CODE START ===
    # Update password_changed_at to invalidate all existing sessions
    user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()

    # Blacklist the token so it can't be reused
    ttl = get_token_ttl_seconds(data.token)
    await blacklist_token(data.token, expiry=ttl)
    # === CHANGED/ADDED CODE END ===

    return {"detail": "Password successfully reset! All other devices have been logged out."}


@router.get("/admin-dashboard")
async def admin_only(admin: User = Depends(require_roles("admin"))):
    return {"msg": "Hello Admin!"}


@router.get("/inventory")
async def view_inventory(user: User = Depends(require_roles("admin", "manager"))):
    return {"msg": "Access granted to admin or Manager"}


@router.get("/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "email_verification":
            raise HTTPException(status_code=400, detail="Invalid token type")
        email = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=400, detail="Link is expired or invalid")

    result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_active:
        return {"detail": "Account already verified."}

    user.is_active = True
    await db.commit()

    ttl = get_token_ttl_seconds(token)
    await blacklist_token(token, expiry=ttl)
    
    return {"detail": "congratulation Your Account is verified"}
