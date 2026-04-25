from sqlalchemy import update, delete, select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging

from app.db.models.cart import Cart, CartItem
from app.db.models.order import Order, OrderItem, OrderStatus
from app.db.models.product import Product

logger = logging.getLogger(__name__)

async def checkout_user_cart(db: AsyncSession, user_id: uuid.UUID, shipping_address: str = None):
    stmt = select(Cart).where(Cart.user_id == user_id).options(
        selectinload(Cart.items).selectinload(CartItem.product)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart khali hai!")

    try:
        # Safety Check: Kahin product delete toh nahi ho gaya checkout se pehle?
        for item in cart.items:
            if not item.product or item.product.is_deleted:
                raise HTTPException(
                    status_code=400,
                    detail=f"Product {item.product.name if item.product else 'Unknown'} ab available nahi hai."
                )

        total_price = sum(item.quantity * item.product.price for item in cart.items)

        new_order = Order(
            user_id=user_id,
            total_price=total_price,
            status=OrderStatus.PENDING,
            shipping_address=shipping_address
        )
        db.add(new_order)
        await db.flush()
        order_id = new_order.id

        for c_item in cart.items:
            # Manual stock check before atomic update
            if c_item.product.stock_quantity < c_item.quantity:
                raise HTTPException(status_code=400, detail=f"{c_item.product.name} ka stock khatam ho gaya hai.")

            stock_update_stmt = (
                update(Product)
                .where(Product.id == c_item.product_id, Product.stock_quantity >= c_item.quantity)
                .values(stock_quantity=Product.stock_quantity - c_item.quantity)
                .returning(Product.stock_quantity)
                .execution_options(synchronize_session=False)
            )

            upd_result = await db.execute(stock_update_stmt)

            # Agar doosra user pehle piece le gaya toh rowcount 0 ayega
            if upd_result.rowcount == 0:
                raise HTTPException(status_code=400, detail="Stock mismatch! Please try again.")

            # Price freeze: OrderItem mein wahi price jayegi jo checkout ke waqt thi
            db.add(OrderItem(
                order_id=order_id,
                product_id=c_item.product_id,
                quantity=c_item.quantity,
                price_at_purchase=c_item.product.price
            ))

        await db.execute(
            delete(CartItem)
            .where(CartItem.cart_id == cart.id)
            .execution_options(synchronize_session=False)
        )
        await db.commit()

        final_stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
        )
        final_result = await db.execute(final_stmt)
        order_obj = final_result.scalar_one()

        return order_obj

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Checkout Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during checkout")


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
