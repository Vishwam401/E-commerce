from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.user import PasswordResetCheck, PasswordResetConfirm, UserCreate, UserOut
from app.services.auth_service import (
    register_user_service,
    resend_verification_service,
    login_service,
    logout_service,
    refresh_token_service,
    forgot_password_service,
    reset_password_service,
    verify_email_service,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    return await register_user_service(user_in=user_in, background_tasks=background_tasks, db=db)


@router.post("/resend-verification")
async def resend_verification(
    email: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    return await resend_verification_service(email=email, background_tasks=background_tasks, db=db)


@router.post("/login")
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    return await login_service(request=request, db=db, form_data=form_data)


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    return await logout_service(token=token)


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    return await refresh_token_service(refresh_token=refresh_token)


@router.post("/forgot-password")
async def forgot_password(
    data: PasswordResetCheck,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    return await forgot_password_service(data=data, background_tasks=background_tasks, db=db)


@router.post("/reset-password")
async def reset_password(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    return await reset_password_service(data=data, db=db)


@router.get("/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    return await verify_email_service(token=token, db=db)


