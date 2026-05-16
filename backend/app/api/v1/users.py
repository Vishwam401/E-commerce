# 1. Standard Python Imports
from typing import List

# 2. Third-Party Imports
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Local Application Imports
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.user import UserOut, UserUpdate
from app.schemas.order import OrderOut

from app.services.user_service import update_user_profile
from app.services import order_service

router = APIRouter()

# 1. Profile Fetch Karo
@router.get("/me", response_model=UserOut)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Login user ki current details return karta hai.
    Authentication token required.
    """
    return current_user

# 2. Profile Update Karo
@router.patch("/me", response_model=UserOut)
async def update_my_profile(
    update_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    User ka name, email ya phone update karta hai.
    Sirf wahi fields update hongi jo body mein bheji jayengi.
    """
    return await update_user_profile(db, current_user.id, update_data)


@router.get("/me/orders", response_model=List[OrderOut])
async def get_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 10,
    offset: int = 0
):

    return await order_service.get_user_orders(db, current_user.id, limit, offset)
