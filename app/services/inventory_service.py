from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.db.models.inventory import StockMovement, StockMovementType
from app.db.models.product import Product
from app.core.exceptions import (
    NotFoundError,
    BadRequestError,
    NegativeStockError,
    StockAdjustmentReasonRequired,
    InvalidStockQuantityError,
)

logger = logging.getLogger(__name__)


async def record_stock_movement(
    db: AsyncSession,
    product: Product,
    movement_type: StockMovementType,
    quantity_changed: int,
    reference_id: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
    performed_by: Optional[uuid.UUID] = None,
) -> StockMovement:
    quantity_before = product.stock_quantity
    quantity_after = quantity_before + quantity_changed

    if quantity_after < 0:
        logger.warning(
            f"[INVENTORY] Negative stock prevented: product={product.id}, "
            f"before={quantity_before}, change={quantity_changed}"
        )
        raise NegativeStockError(
            f"Cannot reduce stock below zero. Current: {quantity_before}, "
            f"Requested change: {quantity_changed}"
        )

    movement = StockMovement(
        product_id=product.id,
        movement_type=movement_type,
        quantity_changed=quantity_changed,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        reference_id=reference_id,
        reason=reason,
        performed_by=performed_by,
    )

    db.add(movement)

    logger.info(
        f"[INVENTORY] Movement recorded: product={product.id}, "
        f"type={movement_type.value}, change={quantity_changed}, "
        f"snapshot={quantity_before}→{quantity_after}"
    )

    return movement


async def admin_adjust_stock(
    db: AsyncSession,
    product_id: uuid.UUID,
    quantity_delta: int,
    reason: str,
    admin_id: uuid.UUID,
) -> StockMovement:
    if not reason or not reason.strip():
        raise StockAdjustmentReasonRequired(
            "Reason is required for stock adjustments."
        )

    stmt = select(Product).where(
        Product.id == product_id,
        Product.is_deleted == False
    ).with_for_update()

    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if not product:
        raise NotFoundError(f"Product {product_id} not found or deleted.")

    movement = await record_stock_movement(
        db=db,
        product=product,
        movement_type=StockMovementType.ADJUSTMENT,
        quantity_changed=quantity_delta,
        reason=reason.strip(),
        performed_by=admin_id,
    )

    product.stock_quantity += quantity_delta
    await db.commit()

    # FIX: Re-fetch movement with product eagerly loaded after commit
    # (After commit, lazy loading fails on async sessions)
    result = await db.execute(
        select(StockMovement)
        .where(StockMovement.id == movement.id)
        .options(joinedload(StockMovement.product))
    )
    movement = result.scalar_one()

    logger.info(
        f"[INVENTORY] Admin adjustment committed: product={product_id}, "
        f"delta={quantity_delta}, by={admin_id}, reason={reason[:50]}"
    )

    return movement


async def admin_restock(
    db: AsyncSession,
    product_id: uuid.UUID,
    quantity_to_add: int,
    reason: Optional[str],
    admin_id: uuid.UUID,
) -> StockMovement:
    if quantity_to_add <= 0:
        raise InvalidStockQuantityError(
            f"Restock quantity must be greater than zero. Received: {quantity_to_add}"
        )

    stmt = select(Product).where(
        Product.id == product_id,
        Product.is_deleted == False
    ).with_for_update()

    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if not product:
        raise NotFoundError(f"Product {product_id} not found or deleted.")

    movement = await record_stock_movement(
        db=db,
        product=product,
        movement_type=StockMovementType.RESTOCK,
        quantity_changed=quantity_to_add,
        reason=reason.strip() if reason else None,
        performed_by=admin_id,
    )

    product.stock_quantity += quantity_to_add
    await db.commit()

   # Re-fetch movement with product eagerly loaded after commit
    # (After commit, lazy loading fails on async sessions)
    result = await db.execute(
        select(StockMovement)
        .where(StockMovement.id == movement.id)
        .options(joinedload(StockMovement.product))
    )
    movement = result.scalar_one()

    logger.info(
        f"[INVENTORY] Restock committed: product={product_id}, "
        f"added={quantity_to_add}, by={admin_id}"
    )

    return movement


async def get_stock_movements(
    db: AsyncSession,
    product_id: uuid.UUID,
    movement_type: Optional[StockMovementType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[StockMovement], int]:
    prod_check = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    if not prod_check.scalar_one_or_none():
        raise NotFoundError(f"Product {product_id} not found.")

    stmt = select(StockMovement).where(
        StockMovement.product_id == product_id
    ).options(
        joinedload(StockMovement.product)
    ).order_by(desc(StockMovement.created_at))

    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    if start_date:
        stmt = stmt.where(StockMovement.created_at >= start_date)
    if end_date:
        stmt = stmt.where(StockMovement.created_at <= end_date)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    return result.scalars().all(), total


async def get_low_stock_products(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Product], int]:
    stmt = select(Product).where(
        Product.stock_quantity <= Product.low_stock_threshold,
        Product.is_deleted == False
    ).options(
        selectinload(Product.category)
    ).order_by(Product.stock_quantity.asc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    return result.scalars().all(), total


async def get_reorder_alerts(
    db: AsyncSession,
) -> List[Product]:
    stmt = select(Product).where(
        Product.stock_quantity <= Product.reorder_point,
        Product.is_deleted == False
    ).options(
        selectinload(Product.category)
    ).order_by(Product.stock_quantity.asc())

    result = await db.execute(stmt)
    return result.scalars().all()


async def get_stock_summary(
    db: AsyncSession,
) -> dict:
    stmt = select(
        func.count(Product.id).filter(
            Product.is_deleted == False
        ).label("total_active"),
        func.count(Product.id).filter(
            Product.stock_quantity == 0,
            Product.is_deleted == False
        ).label("out_of_stock"),
        func.count(Product.id).filter(
            Product.stock_quantity <= Product.low_stock_threshold,
            Product.is_deleted == False,
            Product.stock_quantity > 0
        ).label("low_stock"),
        func.count(Product.id).filter(
            Product.stock_quantity <= Product.reorder_point,
            Product.is_deleted == False
        ).label("reorder_alerts"),
    )

    row = (await db.execute(stmt)).one()

    top_stmt = select(Product).where(
        Product.stock_quantity <= Product.low_stock_threshold,
        Product.is_deleted == False
    ).options(
        selectinload(Product.category)
    ).order_by(Product.stock_quantity.asc()).limit(10)

    top_products = (await db.execute(top_stmt)).scalars().all()

    return {
        "total_active_products": row.total_active,
        "out_of_stock_count": row.out_of_stock,
        "low_stock_count": row.low_stock,
        "reorder_alert_count": row.reorder_alerts,
        "low_stock_products": top_products,
    }


async def update_product_thresholds(
    db: AsyncSession,
    product_id: uuid.UUID,
    low_stock_threshold: Optional[int],
    reorder_point: Optional[int],
    admin_id: uuid.UUID,
) -> Product:
    stmt = select(Product).where(
        Product.id == product_id,
        Product.is_deleted == False
    ).with_for_update()

    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if not product:
        raise NotFoundError(f"Product {product_id} not found.")

    new_threshold = low_stock_threshold if low_stock_threshold is not None else product.low_stock_threshold
    new_reorder = reorder_point if reorder_point is not None else product.reorder_point

    if new_reorder > new_threshold:
        raise BadRequestError(
            f"Reorder point ({new_reorder}) cannot be greater than "
            f"low stock threshold ({new_threshold})."
        )

    if low_stock_threshold is not None:
        product.low_stock_threshold = low_stock_threshold
    if reorder_point is not None:
        product.reorder_point = reorder_point

    await db.commit()
    await db.refresh(product)

    logger.info(
        f"[INVENTORY] Thresholds updated: product={product_id}, "
        f"threshold={product.low_stock_threshold}, reorder={product.reorder_point}, "
        f"by={admin_id}"
    )

    return product