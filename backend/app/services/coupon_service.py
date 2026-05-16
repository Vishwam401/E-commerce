import uuid
import logging
from builtins import str
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.coupon import Coupon, CouponUsage, DiscountType
from app.db.models.cart import Cart
from app.db.models.order import Order
from app.schemas.coupon import ApplyCouponResponse, CouponCreate, CouponUpdate
from app.core.exceptions import (
    NotFoundError,
    BadRequestError,
)

logger = logging.getLogger(__name__)


# 1. Rounding Helper
def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)



# 2. VALIDATE COUPON

async def validate_coupon(
        db: AsyncSession,
        cart: Cart,
        user_id: uuid.UUID,
        code: str
) -> Coupon:

    # Step-1 Normalize -> DB search
    normalized_code = code.strip().upper()

    stmt = select(Coupon).where(Coupon.code == normalized_code)
    result = await db.execute(stmt)
    coupon = result.scalar_one_or_none()

    if not coupon:
        logger.info(f"[COUPON] Not found: {normalized_code}, user={user_id}")
        raise NotFoundError(f"Coupon '{code}' not found")


    #Step 2: Active Check
    if not coupon.is_active:
        logger.info(f"[COUPON] Inactive: {normalized_code}, user={user_id}")
        raise BadRequestError(f"Coupon '{code}' is Inactive")


    # Step 3: Time window check
    now = datetime.now(timezone.utc)
    if now < coupon.valid_from:
        logger.info(f"[COUPON] Not yet active: {normalized_code}, user={user_id}")
        raise BadRequestError(f"Coupon '{code}' is not active yet.")
    if now > coupon.valid_until:
        logger.info(f"[COUPON] Expired: {normalized_code}, user={user_id}")
        raise BadRequestError(f"Coupon '{code}' has expired.")


    # Step 4: Total usage limit (DB count — slightly expensive)
    if coupon.total_used_count >= coupon.max_total_uses:
        logger.info(f"[COUPON] Limit reached: {normalized_code}, used={coupon.total_used_count}")
        raise BadRequestError(f"Coupon '{code}' usage limit reached.")


    # Step 5: Per-User Limit
    user_usage_stmt = (
        select(func.count(CouponUsage.id))
        .where(
            CouponUsage.coupon_id == coupon.id,
            CouponUsage.user_id == user_id,
        )
    )
    user_usage_result = await db.execute(user_usage_stmt)
    user_usage_count = user_usage_result.scalar_one()

    if user_usage_count >= coupon.max_uses_per_user:
        logger.info(f"[COUPON] User limit reached: {normalized_code}, user={user_id}, count={user_usage_count}")
        raise BadRequestError(f"You have already used coupon '{code}' maximum times.")


    # Step 6: Minimum Order Value Check
    cart_subtotal = cart.subtotal_price
    if cart_subtotal < coupon.min_order_value:
        logger.info(
            f"[COUPON] Min order not met: {normalized_code}, subtotal={cart_subtotal}, min={coupon.min_order_value}")
        raise BadRequestError(
            f"Minimum order of ₹{coupon.min_order_value} required for this coupon. "
            f"Your cart: ₹{cart_subtotal}"
        )

    # Step 7: Already applied check
    if cart.coupon_code == normalized_code:
        logger.info(f"[COUPON] Already applied: {normalized_code}, user={user_id}")
        raise BadRequestError(f"Coupon '{code}' is already applied to your cart.")

    logger.info(f"[COUPON] Validated OK: {normalized_code}, user={user_id}")
    return coupon



# 3. CALCULATE DISCOUNT — Pure math, no DB

def calculate_discount(cart_total: Decimal, coupon: Coupon) -> Decimal:

    if coupon.discount_type == DiscountType.FLAT:
        raw_discount = min(coupon.discount_value, cart_total)

    elif coupon.discount_type == DiscountType.PERCENTAGE:
        raw = cart_total * (coupon.discount_value / Decimal('100'))

        #Apply Cap
        if coupon.max_discount_cap is not None:
            raw = min(raw, coupon.max_discount_cap)

        raw_discount = min(raw, cart_total)

    else:
        logger.error(f"[COUPON] Unknown discount type: {coupon.discount_type}")
        raise BadRequestError("Invalid coupon configuration.")

    return round_money(raw_discount)



# 4. APPLY COUPON TO CART
async def apply_coupon_to_cart(
        db:AsyncSession,
        cart: Cart,
        user_id: uuid.UUID,
        code: str,
) ->  ApplyCouponResponse:

    # Validate - fail hone pai exception raise hoga
    coupon = await validate_coupon(db,cart, user_id, code)

    # Calculate discount
    cart_subtotal = cart.subtotal_price
    discount = calculate_discount(cart_subtotal, coupon)

    #Update cart
    cart.coupon_code = coupon.code
    cart.discount_amount = discount
    await db.commit()

    await db.refresh(cart)

    final_total = cart.total_price

    logger.info(
        f"[COUPON] Applied: user={user_id}, code={coupon.code}, "
        f"discount={discount}, subtotal={cart_subtotal}, final={final_total}"
    )

    return ApplyCouponResponse(
        coupon_code=coupon.code,
        discount_amount=discount,
        original_total=cart_subtotal,
        final_total=final_total,
    )



# 5. Remove Coupon From Cart
async def remove_coupon_from_cart(
        db: AsyncSession,
        cart: Cart,
) -> None:

    old_coupon_code = cart.coupon_code

    cart.coupon_code = None
    cart.discount_amount = Decimal('0.00')
    await db.commit()

    if old_coupon_code:
        logger.info(f"[COUPON] Removed from cart: user={cart.user_id}, was={old_coupon_code}")


# 6. USE COUPON IN CHECKOUT — CRITICAL: Race Condition Protection
async def use_coupon_in_checkout(
        db: AsyncSession,
        cart: Cart,
        order: Order,
        user_id: uuid.UUID,
) -> None:

    if not cart.coupon_code:
        return

    normalized_code = cart.coupon_code.strip().upper()

    stmt = (
        select(Coupon)
        .where(Coupon.code == normalized_code)
        .with_for_update()
    )
    result = await db.execute(stmt)
    coupon = result.scalar_one_or_none()

    # Double-check: Coupon abhi bhi exist karta hai?
    if not coupon:
        logger.error(f"[COUPON] Vanished during checkout: {normalized_code}, user={user_id}")
        raise BadRequestError(f"Coupon '{normalized_code}' is no longer available or has been deleted.")

        # Re-validate inside lock — state change ho sakta hai
    now = datetime.now(timezone.utc)
    if not coupon.is_active or now < coupon.valid_from or now > coupon.valid_until:
        logger.warning(f"[COUPON] Invalid at checkout: {normalized_code}, user={user_id}")
        raise BadRequestError("Coupon is no longer valid.")

    if coupon.total_used_count >= coupon.max_total_uses:
        logger.warning(f"[COUPON] Race condition detected: {normalized_code}, user={user_id}")
        raise BadRequestError("Coupon just ran out of uses. Please try another.")

    # Per-user check again (inside lock)
    user_usage_stmt = (
        select(func.count(CouponUsage.id))
        .where(
            CouponUsage.coupon_id == coupon.id,
            CouponUsage.user_id == user_id,
        )
    )
    user_usage_result = await db.execute(user_usage_stmt)
    user_usage_count = user_usage_result.scalar_one()

    if user_usage_count >= coupon.max_uses_per_user:
        raise BadRequestError("Coupon use limit exceeded.")

    # ── All checks passed — now mutate ──

    # 1. Increment counter
    coupon.total_used_count += 1

    # 2. Create usage record
    usage = CouponUsage(
        coupon_id=coupon.id,
        user_id=user_id,
        order_id=order.id,  # ← Order already created, ID available
    )
    db.add(usage)

    # 3. Snapshot on order
    order.coupon_code_snapshot = coupon.code
    order.discount_amount = cart.discount_amount

    # 4. Commit happens in caller (order_service) —
    # yahan sirf add karo, commit mat karo.

    logger.info(
        f"[COUPON] Locked & used: user={user_id}, code={coupon.code}, "
        f"order={order.id}, new_count={coupon.total_used_count}"
    )


# ═══════════════════════════════════════════════════════════════
# ADMIN SERVICE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

async def get_coupon_by_code(db: AsyncSession, code: str) -> Optional[Coupon]:
    """Fetch single coupon by normalized code."""
    normalized = code.strip().upper()
    stmt = select(Coupon).where(Coupon.code == normalized)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def check_code_exists(db: AsyncSession, code: str) -> bool:
    """Duplicate check before create/update."""
    normalized = code.strip().upper()
    existing = await db.execute(
        select(Coupon).where(Coupon.code == normalized)
    )
    return existing.scalar_one_or_none() is not None


async def create_coupon_entity(db: AsyncSession, data: CouponCreate) -> Coupon:
    """Create new coupon from validated schema."""
    coupon = Coupon(
        code=data.code,
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        min_order_value=data.min_order_value,
        max_discount_cap=data.max_discount_cap,
        max_total_uses=data.max_total_uses,
        max_uses_per_user=data.max_uses_per_user,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        is_active=data.is_active,
    )
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return coupon


async def update_coupon_entity(
        db: AsyncSession,
        coupon: Coupon,
        data: CouponUpdate
) -> Coupon:
    """Apply partial updates to existing coupon."""
    update_data = data.model_dump(exclude_unset=True)

    # Code change → duplicate check
    if "code" in update_data:
        new_code = update_data["code"].strip().upper()
        if new_code != coupon.code:
            if await check_code_exists(db, new_code):
                raise BadRequestError(f"Coupon code '{new_code}' already exists.")
        update_data["code"] = new_code

    for field, value in update_data.items():
        setattr(coupon, field, value)

    await db.commit()
    await db.refresh(coupon)
    return coupon


async def deactivate_coupon_entity(db: AsyncSession, coupon: Coupon) -> Coupon:
    """Soft delete — is_active = False."""
    coupon.is_active = False
    await db.commit()
    await db.refresh(coupon)
    return coupon


async def list_coupons_filtered(
        db: AsyncSession,
        active_only: Optional[bool] = None,
        expired: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
) -> tuple[list[Coupon], int]:
    """Return (items, total_count) for pagination."""

    stmt = select(Coupon).order_by(desc(Coupon.created_at))

    if active_only is not None:
        stmt = stmt.where(Coupon.is_active == active_only)

    if expired is not None:
        now = datetime.now(timezone.utc)
        if expired:
            stmt = stmt.where(Coupon.valid_until < now)
        else:
            stmt = stmt.where(Coupon.valid_until >= now)

    if search:
        stmt = stmt.where(Coupon.code.ilike(f"%{search}%"))

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return items, total