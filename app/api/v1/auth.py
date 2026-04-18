from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import User
from app.schemas.user import UserCreate, UserOut
from app.core.security import get_password_hash
import logging

router = APIRouter(prefix='/auth', tags=['Authentication'])

logger = logging.getLogger(__name__)

@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
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
        email=user_in.email.lower(),  # Normalize email for storage
        username=user_in.username,
        hashed_password=hashed_password  # Match field name with model
    )

    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)  
        return new_user
    except Exception as e:
        await db.rollback()  # Rollback on error
        logger.error(f"Error during user registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating user."
        )
