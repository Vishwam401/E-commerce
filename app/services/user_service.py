from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, result
from app.db.models import User
from app.schemas.user import UserUpdate
from app.db.models.order import Order
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, logger
import uuid

from app.db.models.order import OrderItem


async def update_user_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    update_data: UserUpdate
) -> User:
    # 1. Fetch with Row Lock (with_for_update)
    # Taaki race condition na ho email update ke waqt
    stmt = select(User).where(User.id == user_id).with_for_update()
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = update_data.model_dump(exclude_unset=True)

    # 2. Early Guard: Email Unique Check (Loop se bahar)
    if "email" in data:
        new_email = data["email"]
        email_stmt = select(User).where(User.email == new_email, User.id != user_id)
        email_res = await db.execute(email_stmt)
        if email_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Bhai, ye email pehle se registered hai!")

    # 3. Clean Dynamic Update
    for key, value in data.items():
        setattr(user, key, value)

    try:
        await db.commit()
        await db.refresh(user)
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Profile update failed for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during update")



