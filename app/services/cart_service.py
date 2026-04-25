import uuid
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.models.cart import Cart, CartItem
from app.db.models.product import Product


class CartService:

    @staticmethod
    async def get_cart(db: AsyncSession, user_id: uuid.UUID) -> Cart:
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

        # === THE GHOST PRODUCT FIX START ===
        # Agar cart mein koi aisa item hai jiska product Admin ne delete kar diya hai,
        # toh usko silently cart se hata do taaki app crash na ho.
        valid_items = []
        for item in cart.items:
            # Check if product is None (hard deleted) OR is_deleted is True (soft deleted)
            if item.product is None or item.product.is_deleted:
                await db.delete(item)  # Clean the garbage from DB
            else:
                valid_items.append(item)

        if len(valid_items) != len(cart.items):
            await db.commit()  # Save the cleanup
            cart.items = valid_items  # Update current memory
        # === THE GHOST PRODUCT FIX END ===

        return cart

    @staticmethod
    async def update_cart_item_quantity(
            db: AsyncSession,
            user_id: uuid.UUID,
            item_id: uuid.UUID,
            quantity: int
    ):
        # === NEGATIVE QUANTITY FIX START ===
        if quantity <= 0:
            # Agar kisi ne 0 ya negative bheja, toh item hi uda do
            return await CartService.remove_cart_item(db, user_id, item_id)
        # === NEGATIVE QUANTITY FIX END ===

        cart = await CartService.get_cart(db, user_id)

        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found")

        # Check stock
        if item.product.stock_quantity < quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not Enough Stock! Only {item.product.stock_quantity} available."
            )

        item.quantity = quantity
        await db.commit()

        return await CartService.get_cart(db, user_id)



    @staticmethod
    async def add_item_to_cart(
            db: AsyncSession,
            user_id:uuid.UUID,
            product_id: uuid.UUID,
            quantity: int
    ):
        cart = await CartService.get_cart(db, user_id)

        query_product = select(Product).where(Product.id == product_id, Product.is_deleted == False)
        result_product = await db.execute(query_product)
        product = result_product.scalar_one_or_none()

        # If Product Doesn't Exist or is Deleted
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        existing_item = next((item for item in cart.items if str(item.product_id) == str(product_id)), None)

        #Requested Min quantity
        total_requested_quantity = quantity
        if existing_item:
            total_requested_quantity += existing_item.quantity


        # Inventory  Check
        if product.stock_quantity < total_requested_quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not Enough Stock Available! Only {product.stock_quantity} pieces available."
            )

        # Action: Do update or Create New?
        if existing_item:
            existing_item.quantity = total_requested_quantity

        else:
            new_cart_item = CartItem(
                cart_id = cart.id,
                product_id = product_id,
                quantity=quantity
            )
            db.add(new_cart_item)

        await db.commit()

        return await CartService.get_cart(db, user_id)



    @staticmethod
    async def remove_cart_item(
            db: AsyncSession,
            user_id: uuid.UUID,
            item_id: uuid.UUID
    ):
        cart = await CartService.get_cart(db, user_id)

        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found")

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
            raise HTTPException(status_code=404, detail="Item not found")

        if item.quantity > 1:
            item.quantity -= 1
        else:
            await db.delete(item)

        await db.commit()

        db.expire(cart)

        return await CartService.get_cart(db, user_id)
