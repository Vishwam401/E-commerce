from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
import logging

from app.db.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.services.utils import generate_unique_slug
from app.core.exceptions import NotFoundError, DatabaseError
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.services import product_cache_service

logger = logging.getLogger(__name__)


class ProductService:
    @staticmethod
    async def create(db: AsyncSession, obj_in: ProductCreate):
        try:
            slug = await generate_unique_slug(db, Product, obj_in.name)
            product_data = obj_in.model_dump()
            product_data["slug"] = slug

            db_obj = Product(**product_data)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)

            if settings.PRODUCT_CACHE_ENABLED:
                await product_cache_service.invalidate_product_list_cache()

            return db_obj
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Database error creating product: {exc}", exc_info=True)
            raise DatabaseError("Failed to create product")


    @staticmethod
    async def get_active_products(db: AsyncSession, skip: int = 0, limit: int = 20):
        if settings.PRODUCT_CACHE_ENABLED:
            cached_data = await product_cache_service.get_product_list_from_cache(skip, limit)
            if cached_data is not None:
                return cached_data

        try:
            query = (
                select(Product)
                .where(Product.is_deleted == False)
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(query)
            products = result.scalars().all()

            if settings.PRODUCT_CACHE_ENABLED:
                products_data = [
                    ProductResponse.model_validate(p).model_dump(mode='json')
                    for p in products
                ]
                await product_cache_service.set_product_list_in_cache(skip, limit, products_data)

            return products
        except SQLAlchemyError as exc:
            logger.error(f"Database error fetching active products: {exc}", exc_info=True)
            raise DatabaseError("Failed to fetch products")

    @staticmethod
    async def get_all_admin(db: AsyncSession, skip: int = 0, limit: int = 20):
        try:
            query = (
                select(Product)
                .order_by(Product.is_deleted.asc(), Product.name.asc())
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as exc:
            logger.error(f"Database error fetching all products (admin): {exc}", exc_info=True)
            raise DatabaseError("Failed to fetch products")

    @staticmethod
    async def soft_delete(db: AsyncSession, product_id: str):
        try:
            product_uuid = uuid.UUID(product_id)
        except (ValueError, AttributeError):
            raise NotFoundError("Invalid product ID.")

        query = select(Product).where(Product.id == product_uuid)
        result = await db.execute(query)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            raise NotFoundError("Product not found.")

        db_obj.is_deleted = True
        await db.commit()
        
        if settings.PRODUCT_CACHE_ENABLED:
            await product_cache_service.invalidate_product_cache(product_uuid)
            await product_cache_service.invalidate_product_list_cache()
            
        return True

    @staticmethod
    async def get_by_id(db: AsyncSession, product_id: uuid.UUID):
        if settings.PRODUCT_CACHE_ENABLED:
            cached_data = await product_cache_service.get_product_from_cache(product_id)
            if cached_data:
                return cached_data

        query = (
            select(Product)
            .where(Product.id == product_id, Product.is_deleted == False)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(query)
        product = result.scalar_one_or_none()
        
        if product and settings.PRODUCT_CACHE_ENABLED:
            product_dict = ProductResponse.model_validate(product).model_dump(mode='json')
            await product_cache_service.set_product_in_cache(product_id, product_dict)
            
        return product

    @staticmethod
    async def update(
        db: AsyncSession,
        product_id: uuid.UUID,
        update_data: ProductUpdate
    ):
        try:
            query = select(Product).where(Product.id == product_id)
            result = await db.execute(query)
            db_obj = result.scalar_one_or_none()

            if not db_obj:
                raise NotFoundError("Product not found.")

            patch = update_data.model_dump(exclude_unset=True)
            for field, value in patch.items():
                setattr(db_obj, field, value)

            await db.commit()
            await db.refresh(db_obj)
            
            if settings.PRODUCT_CACHE_ENABLED:
                await product_cache_service.invalidate_product_cache(product_id)
                await product_cache_service.invalidate_product_list_cache()
                
            return db_obj
        except NotFoundError:
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Database error updating product {product_id}: {exc}", exc_info=True)
            raise DatabaseError("Failed to update product")
