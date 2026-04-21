from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models.product import Product
from app.schemas.product import ProductCreate
from app.services.utils import generate_unique_slug


class ProductService:
    @staticmethod
    async def create(db: AsyncSession, obj_in: ProductCreate):
        slug = await generate_unique_slug(db, Product, obj_in.name)

        # Pydantic model ko dict mein convert karke slug add kiya
        product_data = obj_in.model_dump()
        product_data["slug"] = slug

        db_obj = Product(**product_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    @staticmethod
    async def get_active_products(db: AsyncSession, skip: int = 0, limit: int = 20):
        # CRITICAL: Yahan hum is_deleted=False ka filter lagayenge
        query = (
            select(Product)
            .where(Product.is_deleted == False)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def soft_delete(db: AsyncSession, product_id: str):
        query = select(Product).where(Product.id == product_id)
        result = await db.execute(query)
        db_obj = result.scalar_one_or_none()

        if db_obj:
            db_obj.is_deleted = True  # Actual DB delete nahi
            await db.commit()
            return True
        return False