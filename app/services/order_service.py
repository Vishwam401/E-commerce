from sqlalchemy import update, delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
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
from app.db.models import Product
from app.core.config import settings
from app.core.exceptions import (
    AppException,
    CartEmptyError,
    InvalidAddressError,
    InsufficientStockError,
    ProductUnavailableError,
    MinimumOrderError,
    PaymentGatewayError,
    PaymentVerificationError,
    OrderCancellationError,
    InvalidStatusTransitionError,
    NotFoundError,
    ForbiddenError,
    DatabaseError,
    ServiceUnavailableError,
)
from app.services.coupon_service import use_coupon_in_checkout

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET_KEY))
logger = logging.getLogger(__name__)

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
    """
    Cart → Order conversion with Razorpay-first flow.
    Razorpay order ID pehle lo, phir DB mein write karo.
    """
    # Fetch cart with products
    stmt = select(Cart).where(Cart.user_id == user_id).options(
        selectinload(Cart.items).selectinload(CartItem.product)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise CartEmptyError()

    # Address verification
    address_stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    address_result = await db.execute(address_stmt)
    address_obj = address_result.scalar_one_or_none()

    if not address_obj or address_obj.is_deleted:
        raise InvalidAddressError()

    address_snapshot = (
        f"{address_obj.full_name}, {address_obj.house_no}, {address_obj.area}, "
        f"{address_obj.city}, {address_obj.state} - {address_obj.pincode}. "
        f"Phone: {address_obj.phone_number}"
    )

    # Pricing calculation
    TAX_RATE = Decimal('0.18')
    SHIPPING_THRESHOLD = Decimal('500.00')
    FLAT_SHIPPING_FEE = Decimal('50.00')

    subtotal = sum(item.quantity * item.product.price for item in cart.items)
    tax_amount = round_money(subtotal * TAX_RATE)
    shipping_amount = Decimal('0.00') if subtotal >= SHIPPING_THRESHOLD else FLAT_SHIPPING_FEE

    discount_amount = cart.discount_amount or Decimal('0.00')

    grand_total = max(subtotal + tax_amount + shipping_amount - discount_amount, Decimal('0.00'))

    amount_in_paise = int(grand_total * 100)
    if amount_in_paise < 100:
        raise MinimumOrderError()

    # Razorpay call FIRST (before any DB write)
    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": str(uuid.uuid4()),
        "payment_capture": 1
    }

    try:
        loop = asyncio.get_running_loop()
        rzp_order = await loop.run_in_executor(
            None, lambda: client.order.create(data=order_data)
        )
    except Exception as exc:
        logger.error(f"Razorpay order creation failed: {exc}", exc_info=True)
        raise PaymentGatewayError("Failed to initialize payment. Please try again.")

    if "id" not in rzp_order:
        raise PaymentGatewayError("Razorpay order ID generation failed")

    # DB writes start here - wrapped in try for DB errors only
    try:
        new_order = Order(
            user_id=user_id,
            address_id=address_id,
            subtotal_price=subtotal,
            tax_price=tax_amount,
            shipping_price=shipping_amount,
            total_price=grand_total,
            status=OrderStatus.PENDING,
            shipping_address_snapshot=address_snapshot,
            coupon_code_snapshot=None,
            discount_amount=Decimal('0.00')
        )
        db.add(new_order)
        await db.flush()
        order_id = new_order.id

        # Stock update & OrderItems
        for c_item in cart.items:
            if not c_item.product or c_item.product.is_deleted:
                raise ProductUnavailableError(str(c_item.product_id))

            if c_item.product.stock_quantity < c_item.quantity:
                raise InsufficientStockError(c_item.product.name)

            # Atomic decrement
            stock_update_stmt = (
                update(Product)
                .where(Product.id == c_item.product_id, Product.stock_quantity >= c_item.quantity)
                .values(stock_quantity=Product.stock_quantity - c_item.quantity)
            )
            upd_result = await db.execute(stock_update_stmt)

            if upd_result.rowcount == 0:
                raise InsufficientStockError(c_item.product.name)

            db.add(OrderItem(
                order_id=order_id,
                product_id=c_item.product_id,
                product_name=c_item.product.name,
                quantity=c_item.quantity,
                price_at_purchase=c_item.product.price
            ))

        # Clear cart
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

        #COUPON USAGE
        if cart.coupon_code:
            await use_coupon_in_checkout(db, cart, new_order, user_id)

        # Transaction record
        new_transaction = Transaction(
            order_id=order_id,
            razorpay_order_id=rzp_order["id"],
            amount=grand_total,
            status="PENDING"
        )
        db.add(new_transaction)

        await db.commit()

        # Fetch final order for response
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

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Database error during checkout: {exc}", exc_info=True)
        raise DatabaseError("Checkout failed due to database error.")
    except AppException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(f"Unexpected checkout error: {exc}", exc_info=True)
        raise ServiceUnavailableError("Checkout failed. Please try again.")


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
            selectinload(Order.items).selectinload(OrderItem.product)
        )
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_order_details(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID):
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .execution_options(populate_existing=True)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found.")
    return order


async def verify_razorpay_payment(
    db: AsyncSession,
    user_id: uuid.UUID,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
):
    stmt = select(Transaction).where(Transaction.razorpay_order_id == razorpay_order_id)
    result = await db.execute(stmt)
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise NotFoundError("Transaction record not found.")

    # Authorization check
    order_stmt = select(Order).where(Order.id == transaction.order_id)
    order_result = await db.execute(order_stmt)
    order = order_result.scalar_one_or_none()

    if not order or order.user_id != user_id:
        logger.warning(
            f"[PAYMENT] Unauthorized verify attempt by user {user_id} "
            f"for order {transaction.order_id}"
        )
        raise ForbiddenError("You are not authorized to verify this payment.")

    # Idempotency check
    if transaction.status == "SUCCESS":
        return {"status": "success", "message": "Payment already verified."}

    try:
        payload = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: client.utility.verify_payment_signature(payload)
        )

        transaction.status = "SUCCESS"
        transaction.razorpay_payment_id = razorpay_payment_id
        transaction.razorpay_signature = razorpay_signature
        order.status = OrderStatus.PAID

        await db.commit()

        logger.info(f"Payment SUCCESS verified for Order: {order.id}")
        return {
            "status": "success",
            "message": "Payment verified successfully.",
            "order_id": order.id
        }

    except SignatureVerificationError:
        transaction.status = "FAILED"
        await db.commit()
        logger.error(
            f"Signature mismatch for RZP_ORDER: {razorpay_order_id}. "
            f"Possible fraud attempt."
        )
        raise PaymentVerificationError()

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Database error during verification: {exc}", exc_info=True)
        raise DatabaseError("Payment verification failed due to database error.")

    except Exception as exc:
        await db.rollback()
        logger.error(f"Verification error: {exc}", exc_info=True)
        raise ServiceUnavailableError("Internal server error during payment verification.")


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
            raise NotFoundError("Order not found.")

        if order.status == OrderStatus.CANCELLED:
            return order

        if order.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            raise OrderCancellationError(order.status.value)

        # Atomic stock rollback
        for item in order.items:
            if not item.product:
                logger.error(f"INTEGRITY ERROR: Product missing for OrderItem {item.id}")
                raise DatabaseError("Data integrity error during cancellation.")

            await db.execute(
                update(Product)
                .where(Product.id == item.product_id)
                .values(stock_quantity=Product.stock_quantity + item.quantity)
            )

        order.status = OrderStatus.CANCELLED
        await db.commit()
        await db.refresh(order)

        logger.info(f"Order {order_id} successfully cancelled by user {user_id}")
        return order

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception(f"Failed to cancel order {order_id}: {exc}")
        raise DatabaseError("Failed to cancel order due to database error.")
    except AppException:
        await db.rollback()
        raise


# ===========================================================================
# ADMIN SERVICE FUNCTIONS
# ===========================================================================

async def get_all_orders_admin(
    db: AsyncSession,
    order_status: OrderStatus | None = None,
    skip: int = 0,
    limit: int = 20
) -> list[Order]:
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
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise NotFoundError("Order not found.")

    if new_status == order.status:
        return order

    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise InvalidStatusTransitionError(
            current=order.status.value,
            target=new_status.value,
            allowed=[s.value for s in allowed]
        )

    order.status = new_status
    await db.commit()
    await db.refresh(order)

    logger.info(
        f"Admin updated order id={order_id} "
        f"status={order.status.value}→{new_status.value}"
    )
    return order