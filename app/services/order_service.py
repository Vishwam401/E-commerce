import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.db.models.cart import Cart, CartItem
from app.db.models.order import Order, OrderItem, OrderStatus



async def checkout_user_cart(db: AsyncSession, user_id:uuid.UUID, shipping_address: str = None):
    # User ki active cart fetch ki hai uske items ke sath
    stmt = select(Cart).where(Cart.user_id == user_id).options(
        selectinload(Cart.items).selectinload(CartItem.product)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your Cart is Empty! Add Some Items"
        )

    # Atomic Transaction starts

    try:
        # Calclulate Total Price
        total_price = sum(item.quantity * item.product.price for item in cart.items)

        # New Order Entry
        new_order = Order(
            user_id=user_id,
            total_price=total_price,
            status=OrderStatus.PENDING,
            shipping_address=shipping_address
        )
        db.add(new_order)
        await db.flush() #ID generate kiya without commit ke


        # Cart ke Items ko Orders ke Items mai shift kiya (Prize Freeze)
        for c_item in cart.items:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=c_item.product_id,
                quantity=c_item.quantity,
                price_at_purchase=c_item.product.price  # Price ko history ke liye save kar liya
            )
            db.add(order_item)

        # Empty Cart
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

        #Final Commit if everything is Okay
        await db.commit()
        await db.refresh(new_order,['items'])
        return new_order

    except Exception as e:
        #if Middle of the Proccess kuchh b Error ai to RollBack
        await db.rollback()
        print(f"Error during checkout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during checkout.Transaction rolled back"
        )


# app/services/order_service.py mein niche add kar

async def get_user_orders(db: AsyncSession, user_id: uuid.UUID):
    """
    User ki history fetch karne ka logic (Service Layer)
    """
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_order_details(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID):
    """
    Specific order detail nikalne ka logic
    """
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items))
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order nahi mila bhai!")
    return order


