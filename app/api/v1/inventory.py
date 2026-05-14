from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.db.session import get_db
from app.api.dependencies import require_roles
from app.db.models.user import User
from app.db.models.product import Product
from app.db.models.inventory import StockMovementType
from app.schemas.inventory import (
    StockMovementResponse,
    AdminAdjustRequest,
    AdminRestockRequest,
    LowStockProductResponse,
    StockSummaryReport,
    ProductThresholdUpdate,
)
from app.services import inventory_service

router = APIRouter()


def _product_to_low_stock_response(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "stock_quantity": p.stock_quantity,
        "low_stock_threshold": p.low_stock_threshold,
        "reorder_point": p.reorder_point,
        "is_at_reorder": p.stock_quantity <= p.reorder_point,
        "category_name": p.category.name if p.category else None,
    }


def _movement_to_response(m) -> dict:
    return {
        "id": m.id,
        "product_id": m.product_id,
        "product_name": m.product.name if m.product else "Unknown",
        "movement_type": m.movement_type,
        "quantity_changed": m.quantity_changed,
        "quantity_before": m.quantity_before,
        "quantity_after": m.quantity_after,
        "reference_id": m.reference_id,
        "reason": m.reason,
        "performed_by": m.performed_by,
        "created_at": m.created_at,
    }


@router.get("/low-stock", response_model=List[LowStockProductResponse])
async def list_low_stock_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    items, total = await inventory_service.get_low_stock_products(db, page, page_size)
    return [_product_to_low_stock_response(p) for p in items]


@router.get("/reorder-alerts", response_model=List[LowStockProductResponse])
async def list_reorder_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    items = await inventory_service.get_reorder_alerts(db)
    return [_product_to_low_stock_response(p) for p in items]


@router.get("/report", response_model=StockSummaryReport)
async def stock_summary_report(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    summary = await inventory_service.get_stock_summary(db)
    return {
        "total_active_products": summary["total_active_products"],
        "out_of_stock_count": summary["out_of_stock_count"],
        "low_stock_count": summary["low_stock_count"],
        "reorder_alert_count": summary["reorder_alert_count"],
        "low_stock_products": [
            _product_to_low_stock_response(p)
            for p in summary["low_stock_products"]
        ],
    }


@router.get("/{product_id}/movements", response_model=List[StockMovementResponse])
async def get_product_movements(
    product_id: uuid.UUID,
    movement_type: Optional[StockMovementType] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    items, total = await inventory_service.get_stock_movements(
        db=db,
        product_id=product_id,
        movement_type=movement_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return [_movement_to_response(m) for m in items]


@router.post(
    "/{product_id}/adjust",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def adjust_stock(
    product_id: uuid.UUID,
    body: AdminAdjustRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    movement = await inventory_service.admin_adjust_stock(
        db=db,
        product_id=product_id,
        quantity_delta=body.quantity_delta,
        reason=body.reason,
        admin_id=current_user.id,
    )
    return _movement_to_response(movement)


@router.post(
    "/{product_id}/restock",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def restock_product(
    product_id: uuid.UUID,
    body: AdminRestockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    movement = await inventory_service.admin_restock(
        db=db,
        product_id=product_id,
        quantity_to_add=body.quantity_to_add,
        reason=body.reason,
        admin_id=current_user.id,
    )
    return _movement_to_response(movement)


@router.patch("/{product_id}/thresholds")
async def update_thresholds(
    product_id: uuid.UUID,
    body: ProductThresholdUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    product = await inventory_service.update_product_thresholds(
        db=db,
        product_id=product_id,
        low_stock_threshold=body.low_stock_threshold,
        reorder_point=body.reorder_point,
        admin_id=current_user.id,
    )
    return {
        "id": product.id,
        "name": product.name,
        "low_stock_threshold": product.low_stock_threshold,
        "reorder_point": product.reorder_point,
    }