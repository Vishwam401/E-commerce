"""
Admin Panel — Product & Order Management
=========================================
All endpoints require the "admin" role.

Product endpoints  (prefix: /api/v1/admin/products)
----------------------------------------------------
POST   /              — Create a new product
GET    /              — List ALL products (active + deleted)
PATCH  /{product_id}  — Update price / stock / description / attributes
DELETE /{product_id}  — Soft-delete a product

Order endpoints  (prefix: /api/v1/admin/orders)
------------------------------------------------
GET    /                        — List ALL orders across the platform
PATCH  /{order_id}/status       — Update order status (with transition validation)
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api import dependencies as deps
from app.db.models.order import Order, OrderItem, OrderStatus
from app.db.session import get_db
from app.schemas.order import OrderOut
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import ProductService

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Valid order-status transitions
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING:    {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID:       {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED:    {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED:  set(),
    OrderStatus.CANCELLED:  set(),
}


# ---------------------------------------------------------------------------
# Request schema for order-status update
# ---------------------------------------------------------------------------
class OrderStatusUpdate(BaseModel):
    new_status: OrderStatus = Field(..., description="Target order status")


# ===========================================================================
# PRODUCT ENDPOINTS
# ===========================================================================

@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Create a new product",
)
async def admin_create_product(
    obj_in: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    """Add a new product to the catalog with auto-generated slug."""
    product = await ProductService.create(db, obj_in)
    logger.info("Admin created product id=%s name=%r", product.id, product.name)
    return product


@router.get(
    "/products",
    response_model=List[ProductResponse],
    summary="[Admin] List ALL products (active + deleted)",
)
async def admin_list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    """Return all products including soft-deleted ones. Sorted: active first."""
    return await ProductService.get_all_admin(db, skip=skip, limit=limit)


@router.patch(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="[Admin] Update product price / stock / description / attributes",
)
async def admin_update_product(
    product_id: uuid.UUID,
    obj_in: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    """
    Partial update — only send the fields you want to change.
    Works on both active and soft-deleted products so admins can
    fix data without having to restore a product first.
    """
    product = await ProductService.update(db, product_id, obj_in)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    logger.info("Admin updated product id=%s", product_id)
    return product


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="[Admin] Soft-delete a product",
)
async def admin_delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    """
    Marks the product as deleted (is_deleted=True).
    The product is hidden from regular user listings but retained in DB
    to preserve order history.
    """
    success = await ProductService.soft_delete(db, str(product_id))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    logger.info("Admin soft-deleted product id=%s", product_id)
    return {"detail": "Product has been deactivated successfully."}


# ===========================================================================
# ORDER ENDPOINTS
# ===========================================================================

@router.get(
    "/orders",
    response_model=List[OrderOut],
    summary="[Admin] List ALL orders across the platform",
)
async def admin_list_orders(
    order_status: Optional[OrderStatus] = Query(
        default=None,
        alias="status",
        description="Filter by order status (pending, paid, processing, shipped, delivered, cancelled)",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    """
    Global order list — no user filter.
    Optionally filter by status. Sorted by created_at DESC (newest first).
    """
    query = (
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if order_status is not None:
        query = query.where(Order.status == order_status)

    result = await db.execute(query)
    return result.scalars().all()


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderOut,
    summary="[Admin] Update order status",
)
async def admin_update_order_status(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    """
    Update an order's status with validated state-machine transitions.

    Allowed transitions:
      pending    → paid | cancelled
      paid       → processing | cancelled
      processing → shipped | cancelled
      shipped    → delivered
      delivered  → (terminal — no further changes)
      cancelled  → (terminal — no further changes)
    """
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    new_status = body.new_status
    if new_status == order.status:
        # Idempotent — no-op, return current state
        return order

    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status transition: '{order.status.value}' → '{new_status.value}'. "
                f"Allowed next states: {[s.value for s in allowed] or 'none (terminal state)'}."
            ),
        )

    order.status = new_status
    await db.commit()
    await db.refresh(order)

    logger.info(
        "Admin updated order id=%s status=%s→%s",
        order_id,
        order.status.value,
        new_status.value,
    )
    return order
