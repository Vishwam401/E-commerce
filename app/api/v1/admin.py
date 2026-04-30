from __future__ import annotations
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import dependencies as deps
from app.db.session import get_db
from app.db.models.order import OrderStatus

from app.schemas.order import OrderOut, OrderStatusUpdate
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate

from app.services.product_service import ProductService
from app.services import order_service

router = APIRouter()


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_product(
    obj_in: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    return await ProductService.create(db, obj_in)


@router.get("/products", response_model=List[ProductResponse])
async def admin_list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    return await ProductService.get_all_admin(db, skip=skip, limit=limit)


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def admin_update_product(
    product_id: uuid.UUID,
    obj_in: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    return await ProductService.update(db, product_id, obj_in)


@router.delete("/products/{product_id}", status_code=status.HTTP_200_OK)
async def admin_delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    await ProductService.soft_delete(db, str(product_id))
    return {"detail": "Product has been deactivated successfully."}


@router.get("/orders", response_model=List[OrderOut])
async def admin_list_orders(
    order_status: Optional[OrderStatus] = Query(None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    return await order_service.get_all_orders_admin(
        db, order_status=order_status, skip=skip, limit=limit
    )


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
async def admin_update_order_status(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    return await order_service.update_order_status_admin(
        db, order_id=order_id, new_status=body.new_status
    )