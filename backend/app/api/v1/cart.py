import uuid
from http import HTTPStatus

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from app.api import dependencies as deps
from app.schemas.cart import CartResponse, CartItemCreate, CartItemUpdate
from app.services.cart_service import CartService


router = APIRouter()

@router.get("/", response_model=CartResponse)
async def get_user_cart(
        db: AsyncSession = Depends(deps.get_db),
        current_user: deps.User = Depends(deps.get_current_active_user),
):
    return await CartService.get_cart(db, current_user.id)


@router.post("/items", response_model=CartResponse, status_code=HTTP_201_CREATED)
async def add_to_cart(
        item_in: CartItemCreate,
        db: AsyncSession = Depends(deps.get_db),
        current_user: deps.User = Depends(deps.get_current_active_user),
):
    return await CartService.add_item_to_cart(
        db,
        user_id=current_user.id,
        product_id=item_in.product_id,
        quantity=item_in.quantity,
    )


@router.put("/items/{item_id}", response_model=CartResponse)
async def update_cart_item(
        item_id: uuid.UUID,
        item_update: CartItemUpdate,
        db: AsyncSession = Depends(deps.get_db),
        current_user: deps.User = Depends(deps.get_current_active_user),
):
    return await CartService.update_cart_item_quantity(
        db,
        user_id=current_user.id,
        item_id=item_id,
        quantity=item_update.quantity,
    )


@router.delete("/items/{item_id}", response_model=CartResponse)
async def remove_cart_item(
        item_id: uuid.UUID,
        db: AsyncSession = Depends(deps.get_db),
        current_user: deps.User = Depends(deps.get_current_active_user),
):
    return await CartService.remove_cart_item(
        db,
        user_id=current_user.id,
        item_id=item_id,
    )


@router.delete("/", response_model=CartResponse)
async def clear_cart(
        db: AsyncSession = Depends(deps.get_db),
        current_user: deps.User = Depends(deps.get_current_active_user),
):
    return await CartService.clear_cart(
        db,
        user_id=current_user.id,
    )


@router.patch("/items/{item_id}/decrease", response_model=CartResponse)
async def decrease_quantity(
        item_id: uuid.UUID,
        db: AsyncSession = Depends(deps.get_db),
        current_user: deps.User = Depends(deps.get_current_active_user),
):
    return await CartService.decrease_item_quantity(
        db,
        user_id=current_user.id,
        item_id=item_id,
    )