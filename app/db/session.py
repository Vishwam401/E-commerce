from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Async Engine
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# session Factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False

)


# Dependency injection for routes
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session