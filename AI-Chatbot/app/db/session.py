from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSession = async_sessionmaker(bind=engine, expire_on_commit=False)


# FastAPI DB Dependency
async def get_db():
    async with AsyncSession() as session:
        yield session
