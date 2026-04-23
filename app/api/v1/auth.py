from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.db.models import User
from app.schemas.user import UserCreate, UserOut, PasswordResetCheck, PasswordResetConfirm
from app.core.security import (
    get_password_hash,
    verify_and_update_password,
    create_access_token,
    create_refresh_token,
    blacklist_token,
    get_token_ttl_seconds,
    create_password_reset_token,
    create_verification_token,
    redis_client,
)
import logging
from redis.exceptions import RedisError
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from app.core.config import settings
from app.api.dependencies import require_roles
from app.utils.email import send_verification_email
from app.core.redis import is_rate_limited

router = APIRouter(prefix='/auth', tags=['Authentication'])

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Add logging to capture input data and validation errors
@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate,background_tasks: BackgroundTasks,db: AsyncSession = Depends(get_db)):

    query = select(User).where(func.lower(User.email) == user_in.email.lower())
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.warning(f"Registration attempt failed: Email {user_in.email} already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists."
        )

    hashed_password = get_password_hash(user_in.password)

    new_user = User(
        email=user_in.email.lower(),
        username=user_in.username,
        hashed_password=hashed_password,
        is_active=False
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
        logger.warning("Registration failed due to duplicate username/email.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists."
        )


@router.post("/login")
async def login(
        request: Request,
        db: AsyncSession = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
     LOGIN ENDPOINT - Detailed logging for debugging
    """
    logger.info(f"[LOGIN] User attempting login with email: {form_data.username}")

    # 1) Rate-limit by client IP (5 attempts / 60s)
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"rate_limit:login:{client_ip}"
    logger.debug(f"[LOGIN] Client IP: {client_ip}")

    try:
        if await is_rate_limited(rate_key, limit=5, window=60, redis_client=redis_client):
            logger.warning(f"[LOGIN] ❌ Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later."
            )
        logger.debug(f"[LOGIN] ✅ Rate limit check passed")
    except RedisError:
        # Fail-open: if Redis is down, do not block all login attempts.
        logger.warning("[LOGIN] ⚠️ Rate limiter unavailable (Redis error). Continuing login flow.")

    # Step 1: Check if user exists
    query = select(User).where(func.lower(User.email) == form_data.username.lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"[LOGIN] ❌ User not found with email: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"[LOGIN] ✅ User found: ID={user.id}, Email={user.email}, is_active={user.is_active}")

    # Step 2: Verify password
    is_valid_password, new_hash = verify_and_update_password(form_data.password, user.hashed_password)
    if not is_valid_password:
        logger.warning(f"[LOGIN] ❌ Invalid password for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"[LOGIN] ✅ Password verified successfully")

    # Step 3: Check if user is active (email verified)
    if not user.is_active:
        logger.warning(f"[LOGIN] ❌ User account NOT VERIFIED (is_active=False). Email: {form_data.username}")
        logger.warning(f"[LOGIN]    → User must verify email first before login")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in."
        )

    logger.info(f"[LOGIN] ✅ User is_active=True, proceeding with token generation")

    # Step 4: Update password hash if needed
    if new_hash:
        user.hashed_password = new_hash
        await db.commit()
        logger.debug(f"[LOGIN] ✅ Password hash updated")

    # Step 5: Create tokens
    access_token = create_access_token(subject=user.username)
    refresh_token = create_refresh_token(subject=user.username)

    logger.info(f"[LOGIN] ✅ Login successful for user: {user.username} (ID: {user.id})")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    try:
        ttl_seconds = get_token_ttl_seconds(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    try:
        await blacklist_token(token, expiry=ttl_seconds)
    except RuntimeError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Logout service unavailable")

    return {"detail": "Successfully logged out"}


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """🔐 REFRESH TOKEN ENDPOINT - Generate new access token"""
    logger.info(f"[REFRESH] Refresh token request received (first 20 chars): {refresh_token[:20]}...")

    try:
        logger.debug(f"[REFRESH] Decoding refresh token with SECRET_KEY")
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        logger.debug(f"[REFRESH] ✅ Token decoded. Payload: {payload}")

        token_type = payload.get("type")
        if token_type != "refresh":
            logger.warning(f"[REFRESH] ❌ Wrong token type. Expected 'refresh', got '{token_type}'")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        logger.debug(f"[REFRESH] ✅ Token type is 'refresh'")

        subject = payload.get("sub")
        logger.debug(f"[REFRESH] Subject (username): {subject}")

        if not subject:
            logger.warning(f"[REFRESH] ❌ No subject in refresh token")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    except JWTError as e:
        logger.warning(f"[REFRESH] ❌ JWT decode error: {str(e)}")
        raise HTTPException(status_code=401, detail="Refresh token expired or invalid")

    # Generate new Access Token
    new_access_token = create_access_token(subject=subject)
    logger.info(f"[REFRESH] ✅ New access token generated for subject: {subject}")

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/admin-only")
async def admin_only_action(current_user:User = Depends(require_roles("admin"))):
    return {'ok':True}


@router.post("/forgot-password")
async def forgot_password(data: PasswordResetCheck,db: AsyncSession= Depends(get_db) ):

    result = await db.execute(select(User).where(func.lower(User.email) == data.email.lower()))
    user= result.scalar_one_or_none()

    if user:
        _ = create_password_reset_token(data.email)

    # Keep response generic to avoid email enumeration.
    return {"detail": "If this email exists, a reset token has been generated (simulated)."}


@router.post("/reset-password")
async def reset_password(data: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
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
    await db.commit()

    return  {"detail": "Password successfully reset!"}


#1. Sirf Admin ke liye
@router.get("/admin-dashboard")
async def admin_only(
        admin: User = Depends(require_roles("admin"))
):
    return {"msg": "Hello Admin!"}

#2 . Jo admin Or Manager Dono ko access de
@router.get("/inventory")
async def view_inventory(
        user: User = Depends(require_roles("admin", "manager"))
):
    return {"msg": "Access granted to admin or Manager"}



@router.get("/verify")
async def verify_email(
        token: str, db:AsyncSession = Depends(get_db)
):
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
        return{"detail": "Account already verified."}

    user.is_active = True
    await db.commit()
    return {"detail": "congratulation Your Account is verified"}
