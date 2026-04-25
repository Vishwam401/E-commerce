from sqlalchemy import update, delete, select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal, ROUND_HALF_UP
import uuid
import logging

from app.db.models.cart import Cart, CartItem
from app.db.models.order import Order, OrderItem, OrderStatus
from app.db.models.product import Product
from app.db.models.address import Address


logger = logging.getLogger(__name__)

def round_money(amount: Decimal):
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

async def checkout_user_cart(db: AsyncSession, user_id: uuid.UUID, address_id: str = None):
    # Cart Fetch with Products
    stmt = select(Cart).where(Cart.user_id == user_id).options(
        selectinload(Cart.items).selectinload(CartItem.product)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart khali hai!")

    # Address verification & Snapshot
    address_stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    address_result = await db.execute(address_stmt)
    address_obj = address_result.scalar_one_or_none()

    if not address_obj or address_obj.is_deleted:
        raise HTTPException(status_code=400, detail="Invalid or deleted shipping address.")

    # Address ka snapshot bana lo taaki kal ko user address delete kare toh bhi order pe record rahe
    address_snapshot = f"{address_obj.full_name}, {address_obj.house_no}, {address_obj.area}, {address_obj.city}, {address_obj.state} - {address_obj.pincode}. Phone: {address_obj.phone_number}"

    try:
        # === Step 3: Industrial Pricing Logic ===
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

        # 2. Create Order with detailed pricing
        new_order = Order(
            user_id=user_id,
            address_id=address_id,
            subtotal_price=subtotal,  # Raw price
            tax_price=tax_amount,  # GST
            shipping_price=shipping_amount,  # Delivery fee
            total_price=grand_total,  # Final Razorpay Amount
            status=OrderStatus.PENDING,
            shipping_address_snapshot=address_snapshot
        )
        db.add(new_order)
        await db.flush()
        order_id = new_order.id

        # 3. Stock Update & OrderItems (Atomic logic)
        for c_item in cart.items:
            # Safety Check: Product active hai?
            if not c_item.product or c_item.product.is_deleted:
                raise HTTPException(status_code=400, detail=f"Product {c_item.product.name} unavailable.")

            # Manual stock check
            if c_item.product.stock_quantity < c_item.quantity:
                raise HTTPException(status_code=400, detail=f"Stock out for {c_item.product.name}")

            # Atomic decrement
            stock_update_stmt = (
                update(Product)
                .where(Product.id == c_item.product_id, Product.stock_quantity >= c_item.quantity)
                .values(stock_quantity=Product.stock_quantity - c_item.quantity)
            )
            upd_result = await db.execute(stock_update_stmt)

            if upd_result.rowcount == 0:
                raise HTTPException(status_code=400, detail="Inventory mismatch, try again.")

            # Create Order Item (Freeze price)
            db.add(OrderItem(
                order_id=order_id,
                product_id=c_item.product_id,
                quantity=c_item.quantity,
                price_at_purchase=c_item.product.price
            ))

        # 4. Clear Cart
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

        await db.commit()

        # 5. Fetch final order object for response
        final_stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
        )
        return (await db.execute(final_stmt)).scalar_one()

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Checkout Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Checkout failed internally.")


async def get_user_orders(db: AsyncSession, user_id: uuid.UUID):
    stmt = (select(Order).where(Order.user_id == user_id)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .order_by(Order.created_at.desc()))
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_order_details(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID):
    stmt = (select(Order).where(Order.id == order_id, Order.user_id == user_id)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .execution_options(populate_existing=True))
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order nahi mila!")
    return order
