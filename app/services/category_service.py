from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, List
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.db.models.product import Category, Product
from app.schemas.product import CategoryCreate, CategoryResponse, ProductCreate
from app.services.utils import generate_unique_slug
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class CatalogService:

    @staticmethod
    async def create_category(db: AsyncSession, obj_in: CategoryCreate):
        try:
            slug = await generate_unique_slug(db, Category, obj_in.name)
            db_obj = Category(
                name=obj_in.name,
                parent_id=obj_in.parent_id,
                slug=slug
            )
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Category creation failed: {exc}")
            raise DatabaseError("Failed to create category.")

    @staticmethod
    async def get_categories(db: AsyncSession):
        try:
            result = await db.execute(select(Category))
            categories = result.scalars().all()

            nodes: Dict[str, CategoryResponse] = {}
            roots: List[CategoryResponse] = []

            for cat in categories:
                nodes[str(cat.id)] = CategoryResponse(
                    id=cat.id,
                    name=cat.name,
                    slug=cat.slug,
                    parent_id=cat.parent_id,
                    sub_categories=[]
                )

            for cat in categories:
                node = nodes[str(cat.id)]
                if cat.parent_id is None:
                    roots.append(node)
                    continue

                parent_node = nodes.get(str(cat.parent_id))
                if parent_node is None:
                    roots.append(node)
                else:
                    parent_node.sub_categories.append(node)

            return roots
        except SQLAlchemyError as exc:
            logger.error(f"Database error fetching categories: {exc}", exc_info=True)
            raise DatabaseError("Failed to fetch categories")

    @staticmethod
    async def create_product(db: AsyncSession, obj_in: ProductCreate):
        try:
            slug = await generate_unique_slug(db, Product, obj_in.name)
            product_data = obj_in.model_dump()
            product_data['slug'] = slug

            db_obj = Product(**product_data)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Product creation failed: {exc}")
            raise DatabaseError("Failed to create product.")

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
    async def soft_delete_product(db: AsyncSession, product_id: str):
        query = select(Product).where(Product.id == product_id)
        result = await db.execute(query)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return False

        db_obj.is_deleted = True
        await db.commit()
        return True