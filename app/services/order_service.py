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
from app.db.models.user import User
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
from app.services.inventory_service import record_stock_movement
from app.db.models.inventory import StockMovementType
from app.services.coupon_service import use_coupon_in_checkout
from ..core.websocket_manager import manager
from .notification_service import (
    NotificationService,
    NotificationPayload,
    NotificationChannel,
    NotificationType,
)

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


def apply_transition(order: Order, new_status: OrderStatus) -> OrderStatus:

    if new_status == order.status:
        return order.status

    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise InvalidStatusTransitionError(
            current=order.status.value,
            target=new_status.value,
            allowed=[s.value for s in allowed]
        )

    old_status = order.status
    order.status = new_status
    return old_status


def _map_status_to_notification(status: OrderStatus) -> NotificationType:

    mapping = {
        OrderStatus.PAID:       NotificationType.PAYMENT_CONFIRMED,
        OrderStatus.PROCESSING: NotificationType.ORDER_STATUS_UPDATE,
        OrderStatus.SHIPPED:    NotificationType.ORDER_SHIPPED,
        OrderStatus.DELIVERED:  NotificationType.ORDER_DELIVERED,
        OrderStatus.CANCELLED:  NotificationType.ORDER_CANCELLED,
    }
    return mapping.get(status, NotificationType.ORDER_STATUS_UPDATE)


async def _fetch_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def checkout_user_cart(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID):
    stmt = select(Cart).where(Cart.user_id == user_id).options(
        selectinload(Cart.items).selectinload(CartItem.product)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise CartEmptyError()

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

        for c_item in cart.items:
            if not c_item.product or c_item.product.is_deleted:
                raise ProductUnavailableError(str(c_item.product_id))

            if c_item.product.stock_quantity < c_item.quantity:
                raise InsufficientStockError(c_item.product.name)

            # Atomically deduct in DB with row-level guard against oversell
            stock_update_stmt = (
                update(Product)
                .where(
                    Product.id == c_item.product_id,
                    Product.stock_quantity >= c_item.quantity
                )
                .values(stock_quantity=Product.stock_quantity - c_item.quantity)
                .execution_options(synchronize_session=False)
            )
            upd_result = await db.execute(stock_update_stmt)

            if upd_result.rowcount == 0:
                raise InsufficientStockError(c_item.product.name)

            await record_stock_movement(
                db=db,
                product=c_item.product,
                movement_type=StockMovementType.SALE,
                quantity_changed=-c_item.quantity,
                reference_id=order_id,
            )

            # NOW sync in-memory to match DB (post-deduction)
            c_item.product.stock_quantity -= c_item.quantity

            db.add(OrderItem(
                order_id=order_id,
                product_id=c_item.product_id,
                product_name=c_item.product.name,
                quantity=c_item.quantity,
                price_at_purchase=c_item.product.price
            ))

        if cart.coupon_code:
            await use_coupon_in_checkout(db, cart, new_order, user_id)

        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        cart.coupon_code = None
        cart.discount_amount = Decimal('0.00')

        new_transaction = Transaction(
            order_id=order_id,
            razorpay_order_id=rzp_order["id"],
            amount=grand_total,
            status="PENDING"
        )
        db.add(new_transaction)

        await db.commit()

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
        .options(selectinload(Order.items).selectinload(OrderItem.product))
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

    order_stmt = select(Order).where(Order.id == transaction.order_id)
    order_result = await db.execute(order_stmt)
    order = order_result.scalar_one_or_none()

    if not order or order.user_id != user_id:
        logger.warning(
            f"[PAYMENT] Unauthorized verify attempt by user {user_id} "
            f"for order {transaction.order_id}"
        )
        raise ForbiddenError("You are not authorized to verify this payment.")

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

        old_status = apply_transition(order, OrderStatus.PAID)

        transaction.status = "SUCCESS"
        transaction.razorpay_payment_id = razorpay_payment_id
        transaction.razorpay_signature = razorpay_signature

        await db.commit()

        logger.info(f"Payment SUCCESS verified for Order: {order.id}")

        # ── WEBSOCKET broadcast (direct — fast, no queue needed) ──────────────
        try:
            await manager.broadcast_to_order(
                order_id=str(order.id),
                message={
                    "event": "order.status_updated",
                    "data": {
                        "order_id": str(order.id),
                        "old_status": old_status.value,
                        "new_status": OrderStatus.PAID.value,
                        "message": "Payment confirmed successfully",
                    },
                },
            )
        except Exception as e:
            logger.warning(f"[WS] Broadcast failed | order={order.id} | err={e}")

        # ── NOTIFICATION (email via Celery) ────────────────────────────────────
        # DB commit ho chuka hai — notification fail hone se order affected nahi hoga.
        # Isliye alag try/except mein hai.
        try:
            user = await _fetch_user(db, order.user_id)
            if user:
                await NotificationService.dispatch(NotificationPayload(
                    user_id=str(user.id),
                    user_email=user.email,
                    order_id=str(order.id),
                    notification_type=NotificationType.PAYMENT_CONFIRMED,
                    data={
                        "username":       getattr(user, "username", None) or "Customer",
                        "order_id_short": str(order.id)[:8],
                        "amount":         float(order.total_price),
                        "payment_id":     razorpay_payment_id,
                        "old_status":     old_status.value,
                        "new_status":     OrderStatus.PAID.value,
                    },
                    channels=[NotificationChannel.EMAIL, NotificationChannel.WEBSOCKET],
                ))
        except Exception as e:
            logger.error(f"[NOTIFY] Payment notify failed for order {order.id}: {e}")

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
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .with_for_update()
    )

    try:
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise NotFoundError("Order not found.")

        if order.status == OrderStatus.CANCELLED:
            return order

        apply_transition(order, OrderStatus.CANCELLED)

        for item in order.items:
            if not item.product:
                logger.error(f"INTEGRITY ERROR: Product missing for OrderItem {item.id}")
                raise DatabaseError("Data integrity error during cancellation.")

            await db.execute(
                update(Product)
                .where(Product.id == item.product_id)
                .values(stock_quantity=Product.stock_quantity + item.quantity)
            )

            prod_result = await db.execute(
                select(Product).where(Product.id == item.product_id)
            )
            product = prod_result.scalar_one_or_none()

            if product:
                await record_stock_movement(
                    db=db,
                    product=product,
                    movement_type=StockMovementType.RETURN,
                    quantity_changed=+item.quantity,
                    reference_id=order_id,
                )

        await db.commit()
        await db.refresh(order)

        logger.info(f"Order {order_id} successfully cancelled by user {user_id}")

        # ── NOTIFICATION ───────────────────────────────────────────────────────
        # DB commit ke baad — notification fail = order still cancelled.
        try:
            user = await _fetch_user(db, order.user_id)
            if user:
                await NotificationService.dispatch(NotificationPayload(
                    user_id=str(user.id),
                    user_email=user.email,
                    order_id=str(order.id),
                    notification_type=NotificationType.ORDER_CANCELLED,
                    data={
                        "username":       getattr(user, "username", None) or "Customer",
                        "order_id_short": str(order.id)[:8],
                        "total_price":    float(order.total_price),
                        "old_status":     OrderStatus.PROCESSING.value,
                        "new_status":     OrderStatus.CANCELLED.value,
                    },
                    channels=[NotificationChannel.EMAIL, NotificationChannel.WEBSOCKET],
                ))
        except Exception as e:
            logger.error(f"[NOTIFY] Cancel notify failed for order {order.id}: {e}")

        return order

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception(f"Failed to cancel order {order_id}: {exc}")
        raise DatabaseError("Failed to cancel order due to database error.")
    except AppException:
        await db.rollback()
        raise


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
    new_status: OrderStatus,
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

    old_status = apply_transition(order, new_status)

    await db.commit()
    await db.refresh(order)

    logger.info(
        f"[ORDER] Admin updated | id={order_id} | "
        f"{old_status.value} → {new_status.value}"
    )

    # ── NOTIFICATION (email via Celery) ────────────────────────────────────────
    # DB commit ho chuka hai — notification side-effect hai, critical nahi.
    try:
        user = await _fetch_user(db, order.user_id)
        if user:
            await NotificationService.dispatch(NotificationPayload(
                user_id=str(user.id),
                user_email=user.email,
                order_id=str(order.id),
                notification_type=_map_status_to_notification(new_status),
                data={
                    "username":       getattr(user, "username", None) or "Customer",
                    "order_id_short": str(order.id)[:8],
                    "old_status":     old_status.value,
                    "new_status":     new_status.value,
                    "total_price":    float(order.total_price),
                    "updated_at":     order.updated_at.isoformat() if order.updated_at else None,
                },
                channels=[NotificationChannel.EMAIL, NotificationChannel.WEBSOCKET],
            ))
    except Exception as e:
        logger.error(f"[NOTIFY] Dispatch failed for order {order.id}: {e}")

    return order