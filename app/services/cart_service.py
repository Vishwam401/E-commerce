import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from app.db.models.cart import Cart, CartItem
from app.db.models.product import Product
from app.core.exceptions import (
    NotFoundError,
    InsufficientStockError,
    ProductUnavailableError,
    DatabaseError,
)

logger = logging.getLogger(__name__)


class CartService:

    @staticmethod
    async def get_cart(db: AsyncSession, user_id: uuid.UUID) -> Cart:
        try:
            query = (
                select(Cart)
                .where(Cart.user_id == user_id)
                .options(
                    selectinload(Cart.items).selectinload(CartItem.product)
                )
                .execution_options(populate_existing=True)
            )
            result = await db.execute(query)
            cart = result.scalar_one_or_none()

            if not cart:
                cart = Cart(user_id=user_id)
                db.add(cart)
                await db.commit()
                db.expire(cart)
                await db.refresh(cart)
                cart.items = []
                return cart

            # Ghost product cleanup
            valid_items = []
            for item in cart.items:
                if item.product is None or item.product.is_deleted:
                    await db.delete(item)
                else:
                    valid_items.append(item)

            if len(valid_items) != len(cart.items):
                await db.commit()
                cart.items = valid_items

            return cart
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Database error fetching cart for user {user_id}: {exc}", exc_info=True)
            raise DatabaseError("Failed to fetch cart")

    @staticmethod
    async def update_cart_item_quantity(
        db: AsyncSession,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
        quantity: int
    ):
        if quantity <= 0:
            return await CartService.remove_cart_item(db, user_id, item_id)

        cart = await CartService.get_cart(db, user_id)

        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise NotFoundError("Cart item not found.")

        if item.product.stock_quantity < quantity:
            raise InsufficientStockError(
                f"Only {item.product.stock_quantity} available."
            )

        item.quantity = quantity
        await db.commit()

        return await CartService.get_cart(db, user_id)

    @staticmethod
    async def add_item_to_cart(
        db: AsyncSession,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int
    ):
        try:
            cart = await CartService.get_cart(db, user_id)

            query_product = select(Product).where(
                Product.id == product_id, Product.is_deleted == False
            )
            result_product = await db.execute(query_product)
            product = result_product.scalar_one_or_none()

            if not product:
                raise NotFoundError("Product not found.")

            existing_item = next(
                (item for item in cart.items if str(item.product_id) == str(product_id)),
                None
            )

            total_requested = quantity
            if existing_item:
                total_requested += existing_item.quantity

            if product.stock_quantity < total_requested:
                raise InsufficientStockError(
                    f"Only {product.stock_quantity} pieces available."
                )

            if existing_item:
                existing_item.quantity = total_requested
            else:
                new_cart_item = CartItem(
                    cart_id=cart.id,
                    product_id=product_id,
                    quantity=quantity
                )
                db.add(new_cart_item)

            await db.commit()
            return await CartService.get_cart(db, user_id)
        except (NotFoundError, InsufficientStockError):
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Database error adding item to cart: {exc}", exc_info=True)
            raise DatabaseError("Failed to add item to cart")

    @staticmethod
    async def remove_cart_item(
        db: AsyncSession,
        user_id: uuid.UUID,
        item_id: uuid.UUID
    ):
        cart = await CartService.get_cart(db, user_id)

        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise NotFoundError("Cart item not found.")

        await db.delete(item)
        await db.commit()

        return await CartService.get_cart(db, user_id)

    @staticmethod
    async def clear_cart(
        db: AsyncSession,
        user_id: uuid.UUID
    ):
        cart = await CartService.get_cart(db, user_id)

        for item in cart.items:
            await db.delete(item)

        await db.commit()
        return await CartService.get_cart(db, user_id)

    @staticmethod
    async def decrease_item_quantity(
        db: AsyncSession,
        user_id: uuid.UUID,
        item_id: uuid.UUID
    ):
        cart = await CartService.get_cart(db, user_id)

        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise NotFoundError("Item not found.")

        if item.quantity > 1:
            item.quantity -= 1
        else:
            await db.delete(item)

        await db.commit()
        db.expire(cart)

        return await CartService.get_cart(db, user_id)
