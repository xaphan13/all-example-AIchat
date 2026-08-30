"""
Health check endpoints.
"""
from fastapi import APIRouter

from src.core.config import settings
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    """Basic health check endpoint."""
    logger.debug("health_check_basic")
    return {
        "status": "online",
        "service": "Multi-Agent Collaboration System",
        "version": "1.0.0"
    }


@router.get("/health")
async def health():
    """Detailed health check."""
    logger.debug("health_check_detailed")
    return {
        "status": "healthy",
        "api_keys": {
            "anthropic": bool(settings.anthropic_api_key),
            "openai": bool(settings.openai_api_key),
            "google": bool(settings.google_api_key),
        },
        "config": {
            "max_concurrent_agents": settings.max_concurrent_agents,
            "agent_timeout": settings.agent_timeout,
        }
    }

