from sqlalchemy import update, delete, select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
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
from app.db.models.product import Product
from app.db.models.address import Address
from app.core.config import settings

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID,settings.RAZORPAY_SECRET_KEY))
logger = logging.getLogger(__name__)

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
                product_name = c_item.product.name,
                quantity=c_item.quantity,
                price_at_purchase=c_item.product.price
            ))

        # 4. Clear Cart
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

        await db.commit()

        # Razor Pay
        amount_in_paise = int(grand_total * 100)

        # Edge Case Protection
        if amount_in_paise < 100:
            raise HTTPException(status_code=400, detail="Minimum order amount must be at least ₹1")

        order_data = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": str(order_id),
            "payment_capture": 1
        }
        #Running sync call in executor so fastAPI doesn't freeze
        loop = asyncio.get_event_loop()
        rzp_order = await loop.run_in_executor(
            None, lambda : client.order.create(data=order_data)
        )

        if "id" not in rzp_order:
            raise Exception("Razorpay order ID generation failed")

        # save transaction in DB
        new_transaction = Transaction(
            order_id=order_id,
            razorpay_order_id=rzp_order["id"],
            amount=grand_total,
            status="PENDING"
        )
        db.add(new_transaction)
        await db.commit()

        # 5. Fetch final order details
        final_stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
        )
        final_order = (await db.execute(final_stmt)).scalar_one()

        # return frontend friendly response
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
        raise HTTPException(status_code=502, detail="Checkout failed internally or gateway down.")


async def get_user_orders(db: AsyncSession, user_id: uuid.UUID):
    stmt = (select(Order).where(Order.user_id == user_id, Order.status == OrderStatus.PAID)
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


async def verify_razorpay_payment(
        db: AsyncSession,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
):
    # 1. Fetch Transaction based on razorpay_order_id
    stmt = select(Transaction).where(Transaction.razorpay_order_id == razorpay_order_id)
    result = await db.execute(stmt)
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction record not found!")

    #2. Race Condition Fix: Check if already processed
    if transaction.status == "SUCCESS":
        return {"status": "success", "message": "Payment already verified."}

    try:
        # 3. SECURITY FIX: Verify Signature using Razorpay SDK
        # SDK synchronous hai, so executor use kiya
        payload = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: client.utility.verify_payment_signature(payload)
        )
        # Agar ye line cross hui , matlab Hacker nahi, real Razorpay ne bheja hai

        # Atomic Database Update
        # Update Transaction
        transaction.status = "SUCCESS"
        transaction.razorpay_payment_id = razorpay_payment_id
        transaction.razorpay_signature = razorpay_signature

        # Fetch and Update Order
        order_stmt = select(Order).where(Order.id == transaction.order_id)
        order_result = await db.execute(order_stmt)
        order = order_result.scalar_one()
        order.status = OrderStatus.PAID

        await db.commit()  # Dono table ek sath update!

        logger.info(f"Payment SUCCESS verified for Order: {order.id}")
        return {"status": "success", "message": "Payment verified successfully", "order_id": order.id}

    except SignatureVerificationError:
        # HACKING ATTEMPT YA FAILED PAYMENT
        transaction.status = "FAILED"
        await db.commit()
        logger.error(f"Signature mismatch for RZP_ORDER: {razorpay_order_id}. Possible fraud attempt.")
        raise HTTPException(status_code=400, detail="Payment verification failed! Invalid signature.")

    except Exception as e:
            await db.rollback()
            logger.error(f"Verification Error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error during verification.")
