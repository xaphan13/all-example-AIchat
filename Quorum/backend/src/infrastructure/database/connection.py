"""
Database connection management using SQLAlchemy with async support.
Handles PostgreSQL connection pooling and session management.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from ...core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        """Initialize database manager."""
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
    
    async def initialize(self):
        """Initialize database engine and session factory."""
        if self._engine is not None:
            logger.warning("Database manager already initialized")
            return
        
        # Convert postgresql:// to postgresql+asyncpg://
        database_url = settings.database_url
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        logger.info(f"Initializing database connection to {settings.database_host}:{settings.database_port}")
        
        try:
            # Create async engine
            self._engine = create_async_engine(
                database_url,
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_pre_ping=True,
                echo=settings.log_level == "DEBUG",
            )
            
            # Create session factory
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            # Test connection
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            logger.info("Database connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Close database connections."""
        if self._engine is None:
            return
        
        logger.info("Closing database connections")
        await self._engine.dispose()
        self._engine = None
        self._session_factory = None
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session.
        
        Usage:
            async with db_manager.session() as session:
                # Use session
                pass
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._engine
    
    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized."""
        return self._engine is not None


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes to get database session.
    
    Usage in routes:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            # Use db session
            pass
    """
    async with db_manager.session() as session:
        yield session

