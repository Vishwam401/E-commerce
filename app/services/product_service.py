from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
import logging

from app.db.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.utils import generate_unique_slug
from app.core.exceptions import NotFoundError, DatabaseError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class ProductService:
    @staticmethod
    async def create(db: AsyncSession, obj_in: ProductCreate):
        slug = await generate_unique_slug(db, Product, obj_in.name)
        product_data = obj_in.model_dump()
        product_data["slug"] = slug

        db_obj = Product(**product_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def get_active_products(db: AsyncSession, skip: int = 0, limit: int = 20):
        query = (
            select(Product)
            .where(Product.is_deleted == False)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_all_admin(db: AsyncSession, skip: int = 0, limit: int = 20):
        query = (
            select(Product)
            .order_by(Product.is_deleted.asc(), Product.name.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

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
        return True

    @staticmethod
    async def get_by_id(db: AsyncSession, product_id: uuid.UUID):
        query = (
            select(Product)
            .where(Product.id == product_id, Product.is_deleted == False)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def update(
        db: AsyncSession,
        product_id: uuid.UUID,
        update_data: ProductUpdate
    ):
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
        return db_obj