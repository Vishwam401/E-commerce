"""
Cart Service — Redis-first with PostgreSQL fallback.

Architecture:
    Read:  Redis cache → DB fallback on miss → repopulate cache
    Write: Validate stock in DB → write to Redis → async sync to DB
    
    This is a Write-Through pattern:
    - User gets instant response from Redis
    - DB sync happens async (fire-and-forget via asyncio.create_task)
    - If Redis is down, all ops fall back to DB (graceful degradation)

Security:
    - Stock validation ALWAYS reads from PostgreSQL (never cached)
    - Prices ALWAYS come from PostgreSQL (never in Redis — prevents price injection)
    - product_id → quantity is the only data in Redis
"""

import uuid
import asyncio
import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import delete as sa_delete

from app.db.models.cart import Cart, CartItem
from app.db.models.product import Product
from app.core.config import settings
from app.core.exceptions import (
    NotFoundError,
    InsufficientStockError,
    ProductUnavailableError,
    DatabaseError,
)
from app.services import cart_cache_service as cache

logger = logging.getLogger(__name__)


class CartService:

    # ══════════════════════════════════════════════════════════════
    # INTERNAL: DB Operations (used as fallback + sync target)
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    async def _get_cart_from_db(db: AsyncSession, user_id: uuid.UUID) -> Cart:
        """
        Read cart from PostgreSQL with eager-loaded items and products.
        Creates a new empty cart if none exists.
        Also cleans up ghost products (deleted/unavailable).

        This is the ORIGINAL get_cart logic — now used as:
        1. Fallback when Redis is unavailable
        2. Source for cache population on miss
        """
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
                await db.refresh(cart, attribute_names=["items"])
                return cart

            # Ghost product cleanup — remove items whose product was deleted
            valid_items = []
            for item in cart.items:
                if item.product is None or item.product.is_deleted:
                    await db.delete(item)
                else:
                    valid_items.append(item)

            if len(valid_items) != len(cart.items):
                await db.commit()
                await db.refresh(cart, attribute_names=["items"])

            return cart
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Database error fetching cart for user {user_id}: {exc}", exc_info=True)
            raise DatabaseError("Failed to fetch cart")

    @staticmethod
    async def _populate_cache_from_cart(cart: Cart) -> None:
        """
        Populate Redis cache from a DB Cart object.
        Called on cache miss to warm up the cache.
        
        Fire-and-forget — if this fails, next read will try again.
        """
        if not settings.CART_CACHE_ENABLED:
            return

        items = {}
        for item in cart.items:
            if item.product and not item.product.is_deleted:
                items[str(item.product_id)] = item.quantity

        await cache.populate_cache_from_db(
            user_id=cart.user_id,
            items=items,
            coupon_code=cart.coupon_code,
            discount_amount=cart.discount_amount or Decimal("0.00"),
        )

    @staticmethod
    async def _build_cart_response_from_cache(
        db: AsyncSession,
        user_id: uuid.UUID,
        cache_data: dict[str, int],
    ) -> Cart:
        """
        Build a Cart ORM object from Redis cache data + DB product details.

        Why we need DB here: Redis only stores product_id → quantity.
        Product name, price, slug, stock, is_deleted come from DB.
        This prevents price injection attacks.

        Also handles ghost product cleanup:
        If a product was deleted after being added to cart,
        we remove it from Redis and skip it in the response.
        """
        # Ensure cart row exists in DB (for cart.id, user_id, timestamps)
        query = (
            select(Cart)
            .where(Cart.user_id == user_id)
        )
        result = await db.execute(query)
        cart = result.scalar_one_or_none()

        if not cart:
            # Cart doesn't exist in DB yet — create it
            cart = Cart(user_id=user_id)
            db.add(cart)
            await db.commit()
            await db.refresh(cart)

        # Fetch all products referenced in the Redis cart
        product_ids = [uuid.UUID(pid) for pid in cache_data.keys()]
        if not product_ids:
            response_cart = Cart(
                id=cart.id, user_id=cart.user_id,
                created_at=cart.created_at, updated_at=cart.updated_at,
                items=[]
            )
            return response_cart

        product_query = select(Product).where(Product.id.in_(product_ids))
        product_result = await db.execute(product_query)
        products = {str(p.id): p for p in product_result.scalars().all()}

        # Build CartItem-like objects, cleaning up ghosts
        items = []
        ghost_product_ids = []

        for product_id_str, quantity in cache_data.items():
            product = products.get(product_id_str)

            if product is None or product.is_deleted:
                # Ghost product — remove from Redis cache
                ghost_product_ids.append(product_id_str)
                continue

            # Find existing CartItem or build a transient one for response
            item = CartItem(
                id=uuid.uuid5(uuid.NAMESPACE_OID, f"{cart.id}_{product_id_str}"),
                cart_id=cart.id,
                product_id=uuid.UUID(product_id_str),
                quantity=quantity,
            )
            # Attach product for the relationship (needed by CartResponse schema)
            item.product = product
            # Use existing CartItem.id if it exists in DB
            items.append(item)

        # Clean up ghosts from Redis (async, non-blocking)
        if ghost_product_ids:
            for ghost_pid in ghost_product_ids:
                await cache.remove_item_from_cache(user_id, uuid.UUID(ghost_pid))
            logger.info(
                f"[CART_CACHE] Cleaned {len(ghost_product_ids)} ghost products "
                f"from cache for user {user_id}"
            )

        # Create a transient Cart so we don't trigger SQLAlchemy lazy-loads on the attached one
        response_cart = Cart(
            id=cart.id,
            user_id=cart.user_id,
            created_at=cart.created_at,
            updated_at=cart.updated_at,
            items=items,
        )

        # Read metadata (coupon)
        meta = await cache.get_cart_meta(user_id)
        if meta:
            response_cart.coupon_code = meta.get("coupon_code")
            discount_str = meta.get("discount_amount", "0.00")
            response_cart.discount_amount = Decimal(discount_str)
        else:
            response_cart.coupon_code = None
            response_cart.discount_amount = Decimal("0.00")

        return response_cart

    @staticmethod
    def _fire_sync_task(
        user_id: uuid.UUID,
    ) -> None:
        """
        Fire-and-forget: schedule async DB sync from Redis state.

        Why asyncio.create_task instead of Celery?
        - Cart is soft state — if sync is lost, Redis still has the data
        - Next read will re-populate from Redis → DB sync will catch up
        - Celery adds broker overhead for a non-critical operation
        - If the server dies mid-sync, the cart is still in Redis (safe)
        """
        try:
            asyncio.create_task(
                CartService._sync_cart_to_db(user_id)
            )
        except RuntimeError:
            # No running event loop (shouldn't happen in FastAPI, but be safe)
            logger.warning(f"[CART_SYNC] No event loop for sync: user={user_id}")

    @staticmethod
    async def _sync_cart_to_db(
        user_id: uuid.UUID,
    ) -> None:
        """
        Sync Redis cart state to PostgreSQL.
        Gets its own isolated DB session since it runs in the background.

        Strategy:
        1. Read full cart from Redis
        2. Read current DB cart
        3. Diff and apply changes (add/update/remove items)
        4. Commit

        This runs as a background task — errors are logged, never raised.
        The user already got their response from Redis.
        """
        from app.db.session import async_session_maker
        
        async with async_session_maker() as db:
            try:
                cache_data = await cache.get_cart_from_cache(user_id)
                if cache_data is None:
                    return  # Cache is empty — nothing to sync

                # Get or create DB cart
                query = (
                    select(Cart)
                    .where(Cart.user_id == user_id)
                    .options(selectinload(Cart.items))
                )
                result = await db.execute(query)
                cart = result.scalar_one_or_none()

                if not cart:
                    cart = Cart(user_id=user_id)
                    db.add(cart)
                    await db.flush()

                # Build index of existing DB items: product_id → CartItem
                db_items = {str(item.product_id): item for item in cart.items}
                cache_product_ids = set(cache_data.keys())
                db_product_ids = set(db_items.keys())

                # Items to ADD (in Redis but not in DB)
                for pid in cache_product_ids - db_product_ids:
                    new_item = CartItem(
                        cart_id=cart.id,
                        product_id=uuid.UUID(pid),
                        quantity=cache_data[pid],
                    )
                    db.add(new_item)

                # Items to UPDATE (in both, but quantity changed)
                for pid in cache_product_ids & db_product_ids:
                    db_item = db_items[pid]
                    if db_item.quantity != cache_data[pid]:
                        db_item.quantity = cache_data[pid]

                # Items to DELETE (in DB but not in Redis)
                for pid in db_product_ids - cache_product_ids:
                    await db.delete(db_items[pid])

                # Sync coupon metadata
                meta = await cache.get_cart_meta(user_id)
                if meta:
                    cart.coupon_code = meta.get("coupon_code")
                    discount_str = meta.get("discount_amount", "0.00")
                    cart.discount_amount = Decimal(discount_str)
                else:
                    cart.coupon_code = None
                    cart.discount_amount = Decimal("0.00")

                await db.commit()
                logger.debug(f"[CART_SYNC] Synced to DB: user={user_id}")

            except SQLAlchemyError as exc:
                await db.rollback()
                logger.error(
                    f"[CART_SYNC] DB sync failed for user {user_id}: {exc}",
                    exc_info=True,
                )
            except Exception as exc:
                logger.error(
                    f"[CART_SYNC] Unexpected sync error for user {user_id}: {exc}",
                    exc_info=True,
                )

    # ══════════════════════════════════════════════════════════════
    # PUBLIC API — Called by cart router
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    async def get_cart(db: AsyncSession, user_id: uuid.UUID) -> Cart:
        """
        Get user's cart — Redis first, DB fallback.

        Flow:
        1. Try Redis HGETALL → cache hit → build response with DB product data
        2. Cache miss → read from PostgreSQL → populate Redis cache → return
        3. Redis error → transparent fallback to PostgreSQL
        """
        if settings.CART_CACHE_ENABLED:
            cache_data = await cache.get_cart_from_cache(user_id)
            if cache_data is not None:
                # Cache HIT — build response using cached items + DB products
                return await CartService._build_cart_response_from_cache(
                    db, user_id, cache_data
                )

        # Cache MISS or cache disabled — read from DB
        cart = await CartService._get_cart_from_db(db, user_id)

        # Populate cache for next time (non-blocking, best-effort)
        if settings.CART_CACHE_ENABLED:
            await CartService._populate_cache_from_cart(cart)

        return cart

    @staticmethod
    async def add_item_to_cart(
        db: AsyncSession,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int,
    ):
        """
        Add item to cart — stock validation via DB, write to Redis, async DB sync.

        Flow:
        1. Validate product exists and has enough stock (DB — always authoritative)
        2. Check current quantity in Redis (if cache hit) or DB
        3. Validate total_requested vs stock
        4. Write to Redis (Lua script — atomic)
        5. Fire async DB sync
        6. Return updated cart
        """
        try:
            # Step 1: Product validation — ALWAYS from DB
            query_product = select(Product).where(
                Product.id == product_id, Product.is_deleted == False
            )
            result_product = await db.execute(query_product)
            product = result_product.scalar_one_or_none()

            if not product:
                raise NotFoundError("Product not found.")

            # Step 2: Get current quantity (Redis first, DB fallback)
            current_qty = 0
            if settings.CART_CACHE_ENABLED:
                cache_data = await cache.get_cart_from_cache(user_id)
                if cache_data is not None:
                    current_qty = cache_data.get(str(product_id), 0)
                else:
                    # Cache miss — check DB for existing item
                    cart = await CartService._get_cart_from_db(db, user_id)
                    existing = next(
                        (i for i in cart.items if str(i.product_id) == str(product_id)),
                        None,
                    )
                    current_qty = existing.quantity if existing else 0
            else:
                cart = await CartService._get_cart_from_db(db, user_id)
                existing = next(
                    (i for i in cart.items if str(i.product_id) == str(product_id)),
                    None,
                )
                current_qty = existing.quantity if existing else 0

            # Step 3: Stock validation
            total_requested = current_qty + quantity
            if product.stock_quantity < total_requested:
                raise InsufficientStockError(
                    f"Only {product.stock_quantity} pieces available."
                )

            # Step 4: Write to Redis (atomic Lua script)
            if settings.CART_CACHE_ENABLED:
                cache_result = await cache.add_item_to_cache(
                    user_id, product_id, quantity
                )
                if cache_result is not None:
                    # Cache write succeeded — fire async DB sync
                    CartService._fire_sync_task(user_id)
                    return await CartService.get_cart(db, user_id)

            # Fallback: Redis failed or disabled — write directly to DB
            cart = await CartService._get_cart_from_db(db, user_id)
            existing_item = next(
                (item for item in cart.items if str(item.product_id) == str(product_id)),
                None,
            )

            if existing_item:
                existing_item.quantity = total_requested
            else:
                new_cart_item = CartItem(
                    cart_id=cart.id,
                    product_id=product_id,
                    quantity=quantity,
                )
                db.add(new_cart_item)

            await db.commit()
            return await CartService._get_cart_from_db(db, user_id)

        except (NotFoundError, InsufficientStockError):
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Database error adding item to cart: {exc}", exc_info=True)
            raise DatabaseError("Failed to add item to cart")

    @staticmethod
    async def update_cart_item_quantity(
        db: AsyncSession,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
        quantity: int,
    ):
        """
        Set exact quantity for a cart item.

        Challenge: The router passes item_id (CartItem.id), but Redis stores by
        product_id. So we need to resolve item_id → product_id first via DB.
        """
        if quantity <= 0:
            return await CartService.remove_cart_item(db, user_id, item_id)

        # Resolve item_id → product_id from DB
        cart = await CartService._get_cart_from_db(db, user_id)
        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise NotFoundError("Cart item not found.")

        # Stock validation — always from DB
        if item.product.stock_quantity < quantity:
            raise InsufficientStockError(
                f"Only {item.product.stock_quantity} available."
            )

        # Write to Redis (absolute set, not increment)
        if settings.CART_CACHE_ENABLED:
            success = await cache.set_item_quantity(
                user_id, item.product_id, quantity
            )
            if success:
                CartService._fire_sync_task(user_id)
                return await CartService.get_cart(db, user_id)

        # Fallback: DB direct
        item.quantity = quantity
        await db.commit()
        return await CartService._get_cart_from_db(db, user_id)

    @staticmethod
    async def remove_cart_item(
        db: AsyncSession,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
    ):
        """
        Remove a single item from cart.

        Same challenge as update: resolve item_id → product_id via DB.
        """
        cart = await CartService._get_cart_from_db(db, user_id)
        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise NotFoundError("Cart item not found.")

        # Remove from Redis
        if settings.CART_CACHE_ENABLED:
            success = await cache.remove_item_from_cache(user_id, item.product_id)
            if success:
                CartService._fire_sync_task(user_id)
                return await CartService.get_cart(db, user_id)

        # Fallback: DB only
        await db.delete(item)
        await db.commit()
        return await CartService._get_cart_from_db(db, user_id)

    @staticmethod
    async def clear_cart(
        db: AsyncSession,
        user_id: uuid.UUID,
    ):
        """
        Clear entire cart — Redis + DB.

        Both are cleared synchronously (not async) because this is a
        destructive operation — we want both stores to agree immediately.
        """
        # Clear Redis
        if settings.CART_CACHE_ENABLED:
            await cache.clear_cart_cache(user_id)

        # Clear DB
        cart = await CartService._get_cart_from_db(db, user_id)
        for item in cart.items:
            await db.delete(item)
        await db.commit()

        return await CartService._get_cart_from_db(db, user_id)

    @staticmethod
    async def decrease_item_quantity(
        db: AsyncSession,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
    ):
        """
        Decrease item quantity by 1. Auto-remove at 0.

        Uses Lua script in Redis for atomic decrement-or-remove.
        """
        # Resolve item_id → product_id
        cart = await CartService._get_cart_from_db(db, user_id)
        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise NotFoundError("Item not found.")

        if settings.CART_CACHE_ENABLED:
            result = await cache.decrease_item_in_cache(user_id, item.product_id)
            if result is not None and result != -1:
                CartService._fire_sync_task(user_id)
                return await CartService.get_cart(db, user_id)

        # Fallback: DB only
        if item.quantity > 1:
            item.quantity -= 1
        else:
            await db.delete(item)

        await db.commit()
        db.expire(cart)
        return await CartService._get_cart_from_db(db, user_id)
