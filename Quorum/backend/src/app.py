"""
FastAPI application entry point.
Provides REST API, Server-Sent Events, and WebSocket endpoints for multi-agent system.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.core.config import settings
from src.core.settings_service import get_settings_service
from src.infrastructure.logging.config import setup_logging, get_logger
from src.api.middleware import LoggingMiddleware, PerformanceLoggingMiddleware
from src.api.routes import health, tasks, websocket, tokens, settings as settings_routes, conversations
from src.infrastructure.database import db_manager
from src.infrastructure.database.models import Base
from src.infrastructure.database.settings_models import AppSettings

# Initialize logging first
setup_logging(
    log_level=settings.log_level,
    json_logs=settings.log_json,
    log_file=settings.log_file if settings.log_file else None
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with database initialization."""
    logger.info(
        "application_starting",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
    
    # Initialize database
    try:
        logger.info("initializing_database")
        await db_manager.initialize()
        
        # Check if database tables exist, if not create them
        async with db_manager.engine.begin() as conn:
            # Enable pgvector extension
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("pgvector_extension_enabled")
            except Exception as e:
                logger.warning("pgvector_extension_already_exists_or_not_needed", error=str(e))
            
            # Create all tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(AppSettings.metadata.create_all)
            logger.info("database_tables_verified")
        
        logger.info("database_initialization_complete")
        
        # Initialize SettingsService with database manager
        settings_service = get_settings_service(db_manager)
        logger.info("settings_service_initialized_with_database")
        
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e), exc_info=True)
        logger.warning("continuing_without_database")
        # Initialize SettingsService without database (will use env vars)
        get_settings_service()
    
    yield
    
    # Cleanup
    logger.info("application_shutdown")
    await db_manager.close()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Initialize FastAPI app
    app = FastAPI(
        title="Multi-Agent Collaboration System",
        description="AI agents working together to accomplish complex tasks",
        version="1.0.0",
        lifespan=lifespan
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add logging middleware
    app.add_middleware(
        LoggingMiddleware,
        exclude_paths={"/", "/health"}
    )

    # Add performance monitoring (optional, can be enabled/disabled)
    if settings.log_level == "DEBUG":
        app.add_middleware(
            PerformanceLoggingMiddleware,
            slow_request_threshold_ms=1000.0
        )

    # Include routers
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(websocket.router)
    app.include_router(tokens.router)
    app.include_router(settings_routes.router)
    app.include_router(conversations.router)

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.app:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info"
    )

