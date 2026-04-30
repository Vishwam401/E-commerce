from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import uuid
import logging

from app.db.models import User
from app.schemas.user import UserUpdate
from app.core.exceptions import (
    NotFoundError,
    EmailAlreadyExistsError,
    DatabaseError,
)

logger = logging.getLogger(__name__)


async def update_user_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    update_data: UserUpdate
) -> User:
    stmt = select(User).where(User.id == user_id).with_for_update()
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User not found.")

    data = update_data.model_dump(exclude_unset=True)

    if "email" in data:
        new_email = data["email"]
        email_stmt = select(User).where(
            User.email == new_email, User.id != user_id
        )
        email_res = await db.execute(email_stmt)
        if email_res.scalar_one_or_none():
            raise EmailAlreadyExistsError()

    for key, value in data.items():
        setattr(user, key, value)

    try:
        await db.commit()
        await db.refresh(user)
        return user
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Profile update failed for user {user_id}: {exc}")
        raise DatabaseError("Profile update failed due to database error.")