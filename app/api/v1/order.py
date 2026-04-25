from typing import List
import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.schemas.order import OrderCreate, OrderOut
from app.db.models.user import User


from app.services.order_service import (
    checkout_user_cart,
    get_user_orders,
    get_order_details
)

router = APIRouter()

# 1. Checkout (Logic: Convert Cart -> Order + Clear Cart)
@router.post("/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_checkout(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ye service function internally cart khali kar deta hai
    return await checkout_user_cart(db, current_user.id, order_in.shipping_address)



# 2. Order History (Logic: Simple Select Query)
@router.get("/", response_model=List[OrderOut])
async def list_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_user_orders(db, current_user.id)



# 3. Order Detail (Logic: Select by ID + Security Check)
@router.get("/{order_id}", response_model=OrderOut)
async def view_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    order = await get_order_details(db, order_id, current_user.id)
    return order