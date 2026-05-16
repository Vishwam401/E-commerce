from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import re


async def generate_unique_slug(db: AsyncSession, model, name: str) -> str:
    """Generate slug from name and ensure uniqueness for given model.

    Example: 'iPhone 15 Pro Max!' -> 'iphone-15-pro-max' and append -1, -2 if needed.
    """
    base_slug = re.sub(r"[^\w\s-]", "", name).lower()
    base_slug = re.sub(r"[-\s]+", "-", base_slug).strip("-")

    slug = base_slug
    counter = 1

    while True:
        query = select(model).where(model.slug == slug)
        result = await db.execute(query)
        if not result.scalar_one_or_none():
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1

