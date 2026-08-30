"""
Database initialization script.
Creates tables and enables pgvector extension.
"""
import asyncio
import logging
from sqlalchemy import text

from .connection import DatabaseManager
from .models import Base
from ...core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_db():
    """Initialize database with pgvector extension and create all tables."""
    db = DatabaseManager()
    
    try:
        logger.info("Initializing database connection...")
        await db.initialize()
        
        logger.info("Enabling pgvector extension...")
        async with db.engine.begin() as conn:
            # Enable pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension enabled")
            
            # Create all tables
            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    
    finally:
        await db.close()


async def drop_db():
    """Drop all tables. WARNING: This will delete all data!"""
    db = DatabaseManager()
    
    try:
        logger.warning("Dropping all database tables...")
        await db.initialize()
        
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("All tables dropped")
        
    except Exception as e:
        logger.error(f"Error dropping database: {e}")
        raise
    
    finally:
        await db.close()


async def reset_db():
    """Reset database by dropping and recreating all tables."""
    logger.warning("Resetting database - all data will be lost!")
    await drop_db()
    await init_db()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "init":
            asyncio.run(init_db())
        elif command == "drop":
            asyncio.run(drop_db())
        elif command == "reset":
            asyncio.run(reset_db())
        else:
            print(f"Unknown command: {command}")
            print("Usage: python init_db.py [init|drop|reset]")
            sys.exit(1)
    else:
        # Default to init
        asyncio.run(init_db())

