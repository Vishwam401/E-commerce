from sqlalchemy import update, delete, select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal, ROUND_HALF_UP
import uuid
import logging
import razorpay
from razorpay.errors import SignatureVerificationError
import asyncio
from app.db.models.cart import Cart, CartItem
from app.db.models.order import Order, OrderItem, OrderStatus
from app.db.models.transaction import Transaction

from app.db.models.address import Address
from app.core.config import settings
from app.db.models import Product

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET_KEY))
logger = logging.getLogger(__name__)

# State Machine: Ye rule banata hai ki kaunsa status kiske baad aa sakta hai
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def round_money(amount: Decimal):
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


async def checkout_user_cart(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID):
    # Cart Fetch with Products
    stmt = select(Cart).where(Cart.user_id == user_id).options(
        selectinload(Cart.items).selectinload(CartItem.product)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    # Address verification & Snapshot
    address_stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    address_result = await db.execute(address_stmt)
    address_obj = address_result.scalar_one_or_none()

    if not address_obj or address_obj.is_deleted:
        raise HTTPException(status_code=400, detail="Invalid or deleted shipping address.")

    # Address ka snapshot bana lo taaki kal ko user address delete kare toh bhi order pe record rahe
    address_snapshot = f"{address_obj.full_name}, {address_obj.house_no}, {address_obj.area}, {address_obj.city}, {address_obj.state} - {address_obj.pincode}. Phone: {address_obj.phone_number}"

    try:
        TAX_RATE = Decimal('0.18')  # 18% GST
        SHIPPING_THRESHOLD = Decimal('500.00')
        FLAT_SHIPPING_FEE = Decimal('50.00')

        # A. Subtotal (Items * Price)
        subtotal = sum(item.quantity * item.product.price for item in cart.items)

        # B. Tax calculation
        tax_amount = round_money(subtotal * TAX_RATE)

        # C. Shipping calculation
        shipping_amount = Decimal('0.00') if subtotal >= SHIPPING_THRESHOLD else FLAT_SHIPPING_FEE

        # D. Grand Total
        grand_total = subtotal + tax_amount + shipping_amount

        # Edge Case Protection — check before any DB write
        amount_in_paise = int(grand_total * 100)
        if amount_in_paise < 100:
            raise HTTPException(status_code=400, detail="Minimum order amount must be at least ₹1")

        # ✅ BUG FIX: Razorpay call PEHLE karo, DB commit baad mein.
        # Pehle: stock cut -> cart clear -> DB commit -> PHIR Razorpay
        # Problem: Razorpay fail hone pe stock permanently cut ho jaata tha (stock leak).
        # Fix: Pehle Razorpay se order ID lo. Agar Razorpay fail hua toh kuch bhi DB mein save nahi hoga.
        order_data = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": str(uuid.uuid4()),  # temporary receipt, real order_id baad mein milega
            "payment_capture": 1
        }

        # ✅ FIX: asyncio.get_event_loop() deprecated hai Python 3.10+ mein — get_running_loop() use karo
        loop = asyncio.get_running_loop()
        rzp_order = await loop.run_in_executor(
            None, lambda: client.order.create(data=order_data)
        )

        if "id" not in rzp_order:
            raise Exception("Razorpay order ID generation failed")

        # ✅ Ab DB mein likhte hain — sirf tab jab Razorpay ne order ID de diya
        new_order = Order(
            user_id=user_id,
            address_id=address_id,
            subtotal_price=subtotal,
            tax_price=tax_amount,
            shipping_price=shipping_amount,
            total_price=grand_total,
            status=OrderStatus.PENDING,
            shipping_address_snapshot=address_snapshot
        )
        db.add(new_order)
        await db.flush()
        order_id = new_order.id

        # Stock Update & OrderItems (Atomic logic)
        for c_item in cart.items:
            if not c_item.product or c_item.product.is_deleted:
                raise HTTPException(status_code=400, detail=f"Product '{c_item.product_id}' is unavailable.")

            if c_item.product.stock_quantity < c_item.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for '{c_item.product.name}'.")

            # Atomic decrement — race condition safe
            stock_update_stmt = (
                update(Product)
                .where(Product.id == c_item.product_id, Product.stock_quantity >= c_item.quantity)
                .values(stock_quantity=Product.stock_quantity - c_item.quantity)
            )
            upd_result = await db.execute(stock_update_stmt)

            if upd_result.rowcount == 0:
                raise HTTPException(status_code=400,
                                    detail=f"Stock conflict for '{c_item.product.name}'. Please try again.")

            # Create Order Item (Freeze price at time of purchase)
            db.add(OrderItem(
                order_id=order_id,
                product_id=c_item.product_id,
                product_name=c_item.product.name,
                quantity=c_item.quantity,
                price_at_purchase=c_item.product.price
            ))

        # Clear Cart
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

        # Save Transaction record
        new_transaction = Transaction(
            order_id=order_id,
            razorpay_order_id=rzp_order["id"],
            amount=grand_total,
            status="PENDING"
        )
        db.add(new_transaction)

        # ✅ Single commit — Razorpay already succeeded, ab DB atomically save karo
        await db.commit()

        # Fetch final order details for response
        final_stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
        )
        final_order = (await db.execute(final_stmt)).scalar_one()

        return {
            "order": final_order,
            "payment_details": {
                "razorpay_order_id": rzp_order["id"],
                "amount": rzp_order["amount"],
                "currency": rzp_order["currency"],
                "key": settings.RAZORPAY_KEY_ID
            }
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Checkout Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=502, detail="Checkout failed. Please try again.")


async def get_user_orders(
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 10,
        offset: int = 0
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .options(
            selectinload(Order.items)
            .selectinload(OrderItem.product)
        )
        .order_by(Order.created_at.desc())  # Latest orders pehle
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    # saclar_one_or_none() nahi use kre bcz list chaiye
    orders = result.scalars().all()
    return orders


async def get_order_details(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID):
    stmt = (select(Order).where(Order.id == order_id, Order.user_id == user_id)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .execution_options(populate_existing=True))
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


# ✅ BUG FIX: user_id parameter add kiya — payment verify karne se pehle check karo
# ki ye transaction is user ka hai. Pehle koi bhi razorpay_order_id bhej ke
# kisi aur ka order PAID mark karwa sakta tha (agar signature bypass hota).
async def verify_razorpay_payment(
        db: AsyncSession,
        user_id: uuid.UUID,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
):
    # 1. Fetch Transaction based on razorpay_order_id
    stmt = select(Transaction).where(Transaction.razorpay_order_id == razorpay_order_id)
    result = await db.execute(stmt)
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction record not found.")

    # ✅ FIX: Verify that this transaction's order belongs to the requesting user
    order_stmt = select(Order).where(Order.id == transaction.order_id)
    order_result = await db.execute(order_stmt)
    order = order_result.scalar_one_or_none()

    if not order or order.user_id != user_id:
        logger.warning(f"[PAYMENT] Unauthorized verify attempt by user {user_id} for order {transaction.order_id}")
        raise HTTPException(status_code=403, detail="You are not authorized to verify this payment.")

    # Race Condition Fix: Already processed check
    if transaction.status == "SUCCESS":
        return {"status": "success", "message": "Payment already verified."}

    try:
        # Verify Signature using Razorpay SDK
        payload = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        # ✅ FIX: asyncio.get_event_loop() → get_running_loop()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: client.utility.verify_payment_signature(payload)
        )

        # Atomic Database Update
        transaction.status = "SUCCESS"
        transaction.razorpay_payment_id = razorpay_payment_id
        transaction.razorpay_signature = razorpay_signature
        order.status = OrderStatus.PAID

        await db.commit()

        logger.info(f"Payment SUCCESS verified for Order: {order.id}")
        return {"status": "success", "message": "Payment verified successfully.", "order_id": order.id}

    except SignatureVerificationError:
        transaction.status = "FAILED"
        await db.commit()
        logger.error(f"Signature mismatch for RZP_ORDER: {razorpay_order_id}. Possible fraud attempt.")
        raise HTTPException(status_code=400, detail="Payment verification failed. Invalid signature.")

    except Exception as e:
        await db.rollback()
        logger.error(f"Verification Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during payment verification.")


async def process_order_cancellation(
        db: AsyncSession,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
) -> Order:
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product)
        )
        .with_for_update()
    )

    try:
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")

        if order.status == OrderStatus.CANCELLED:
            return order

        if order.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel order in {order.status} status."
            )

        # ATOMIC stock rollback
        for items in order.items:
            if not items.product:
                logger.error(f"INTEGRITY ERROR: Product missing for OrderItem {items.id}")
                raise HTTPException(status_code=500, detail="Data integrity error")

            # memory mai update krne ki jagah sidha db mai query run kri hai
            await db.execute(
                update(Product)
                .where(Product.id == items.product_id)
                .values(stock_quantity=Product.stock_quantity + items.quantity)
            )

        # order status update
        order.status = OrderStatus.CANCELLED

        # final commit
        await db.commit()
        await db.refresh(order)

        logger.info(f"Order {order_id} successfully cancelled by user {user_id}")
        return order

    except Exception as e:
        await db.rollback()  # <--- IMPORTANT: Kuch bhi phate toh rollback!
        logger.exception(f"Failed to cancel order {order_id}")
        raise e


# ===========================================================================
# ADMIN SERVICE FUNCTIONS
# ===========================================================================

async def get_all_orders_admin(
        db: AsyncSession,
        order_status: OrderStatus | None = None,
        skip: int = 0,
        limit: int = 20
) -> list[Order]:
    """Admin ke liye saare platform ke orders lane ka logic"""
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


async def update_order_status_admin(
        db: AsyncSession,
        order_id: uuid.UUID,
        new_status: OrderStatus
) -> Order:
    """Order ka status check karke DB mein update karne ka logic (with state machine validation)"""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    # Agar same status bhej diya toh wahi return kardo
    if new_status == order.status:
        return order

    # State Machine validation
    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status transition: '{order.status.value}' → '{new_status.value}'. "
                f"Allowed next states: {[s.value for s in allowed] or 'none (terminal state)'}."
            ),
        )

    # DB update
    order.status = new_status
    await db.commit()
    await db.refresh(order)

    logger.info(f"Admin updated order id={order_id} status={order.status.value}→{new_status.value}")
    return order