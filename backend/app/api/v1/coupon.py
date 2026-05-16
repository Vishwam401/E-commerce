from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.session import get_db
from app.api.dependencies import get_current_user, require_roles
from app.db.models.user import User
from app.db.models.coupon import Coupon, CouponUsage
from app.schemas.coupon import (
    CouponCreate,
    CouponUpdate,
    CouponResponse,
    ApplyCouponRequest,
    ApplyCouponResponse,
    CouponAdminListResponse,
)

from app.services.cart_service import CartService
from app.core.exceptions import NotFoundError, BadRequestError

from app.services.coupon_service import (
    apply_coupon_to_cart,
    remove_coupon_from_cart,
    # Admin functions:
    get_coupon_by_code,
    check_code_exists,
    create_coupon_entity,
    update_coupon_entity,
    deactivate_coupon_entity,
    list_coupons_filtered,
)

router = APIRouter()

# ═══════════════════════════════════════════════════════════════
# USER ROUTES
# ═══════════════════════════════════════════════════════════════

@router.post("/cart/apply-coupon", response_model=ApplyCouponResponse)
async def apply_coupon(
        request: ApplyCouponRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    cart = await CartService.get_cart(db, current_user.id)
    return await apply_coupon_to_cart(
        db=db, cart=cart, user_id=current_user.id, code=request.code,
    )


@router.delete("/cart/remove-coupon")
async def remove_coupon(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    cart = await CartService.get_cart(db, current_user.id)
    await remove_coupon_from_cart(db, cart)
    return {"status": "removed"}


# ═══════════════════════════════════════════════════════════════
# ADMIN ROUTES — Ab thin hain, sirf service calls
# ═══════════════════════════════════════════════════════════════

@router.post("/admin/coupons", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
async def create_coupon(
        data: CouponCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_roles("admin")),
):
    if await check_code_exists(db, data.code):
        raise BadRequestError(f"Coupon code '{data.code}' already exists.")

    return await create_coupon_entity(db, data)


@router.get("/admin/coupons", response_model=CouponAdminListResponse)
async def list_coupons(
        active_only: Optional[bool] = Query(None),
        expired: Optional[bool] = Query(None),
        search: Optional[str] = Query(None, min_length=1),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_roles("admin")),
):
    items, total = await list_coupons_filtered(
        db, active_only, expired, search, page, page_size
    )

    return CouponAdminListResponse(
        items=items, total=total, page=page, page_size=page_size,
    )


@router.get("/admin/coupons/{code}", response_model=CouponResponse)
async def get_coupon_detail(
        code: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_roles("admin")),
):
    coupon = await get_coupon_by_code(db, code)
    if not coupon:
        raise NotFoundError(f"Coupon '{code}' not found.")
    return coupon


@router.patch("/admin/coupons/{code}", response_model=CouponResponse)
async def update_coupon(
        code: str,
        data: CouponUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_roles("admin")),
):
    coupon = await get_coupon_by_code(db, code)
    if not coupon:
        raise NotFoundError(f"Coupon '{code}' not found.")

    return await update_coupon_entity(db, coupon, data)


@router.patch("/admin/coupons/{code}/deactivate", response_model=CouponResponse)
async def deactivate_coupon(
        code: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_roles("admin")),
):
    coupon = await get_coupon_by_code(db, code)
    if not coupon:
        raise NotFoundError(f"Coupon '{code}' not found.")

    return await deactivate_coupon_entity(db, coupon)


