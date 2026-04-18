from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.db.session import get_db
from app.db.models import User
from app.schemas.user import UserCreate, UserOut
from app.core.security import get_password_hash
import logging
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import verify_and_update_password, create_access_token



router = APIRouter(prefix='/auth', tags=['Authentication'])

logger = logging.getLogger(__name__)

# Add logging to capture input data and validation errors
@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
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
            hashed_password=hashed_password
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        logger.exception("Registration failed due to integrity constraint violation.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists."
        )
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during user registration.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating user."
        )


@router.post("/login")
async def login(
        db: AsyncSession = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends(),
):

    query = select(User).where(func.lower(User.email) == form_data.username.lower())
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Failed login attempt for email: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_valid_password, new_hash = verify_and_update_password(form_data.password, user.hashed_password)
    if not is_valid_password:
        logger.warning(f"Failed login attempt for email: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if new_hash:
        user.hashed_password = new_hash
        await db.commit()

    # Create access token with user email as the subject
    access_token = create_access_token(subject=user.username)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
