"""
Settings service for accessing application settings with database fallback.
Provides a unified interface to get settings from database or environment variables.
"""
from typing import Optional
from src.core.config import settings as env_settings
from src.infrastructure.database import DatabaseManager, SettingsRepository
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class SettingsService:
    """Service for accessing application settings."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize settings service with optional database manager."""
        self.db_manager = db_manager
        self._cached_settings = None
    
    async def get_openrouter_api_key(self) -> str:
        """Get OpenRouter API key from database or fallback to environment."""
        settings = await self._get_settings()
        key = settings.get("openrouter_api_key", "")
        if key and len(key) > 10:
            return key
        return env_settings.openrouter_api_key
    
    async def get_max_concurrent_agents(self) -> int:
        """Get max concurrent agents setting."""
        settings = await self._get_settings()
        return settings.get("max_concurrent_agents", env_settings.max_concurrent_agents)
    
    async def get_agent_timeout(self) -> int:
        """Get agent timeout setting."""
        settings = await self._get_settings()
        return settings.get("agent_timeout", env_settings.agent_timeout)
    
    async def get_embedding_model(self) -> str:
        """Get embedding model setting."""
        settings = await self._get_settings()
        return settings.get("embedding_model", env_settings.embedding_model)
    
    async def _get_settings(self) -> dict:
        """
        Get settings from database or return cached/default values.
        Falls back to environment variables if database is unavailable.
        """
        # Try to get from database if available
        if self.db_manager and self.db_manager.is_initialized:
            try:
                async with self.db_manager.session() as session:
                    app_settings = await SettingsRepository.get_or_create(session)
                    self._cached_settings = {
                        "openrouter_api_key": app_settings.openrouter_api_key,
                        "max_concurrent_agents": app_settings.max_concurrent_agents,
                        "agent_timeout": app_settings.agent_timeout,
                        "embedding_model": app_settings.embedding_model,
                        "embedding_dimension": app_settings.embedding_dimension,
                        "vector_similarity_threshold": app_settings.vector_similarity_threshold,
                    }
                    return self._cached_settings
            except Exception as e:
                logger.warning("failed_to_get_settings_from_database", error=str(e))
        
        # Return cached settings if available
        if self._cached_settings:
            return self._cached_settings
        
        # Return default settings from environment
        return {
            "openrouter_api_key": env_settings.openrouter_api_key,
            "max_concurrent_agents": env_settings.max_concurrent_agents,
            "agent_timeout": env_settings.agent_timeout,
            "embedding_model": env_settings.embedding_model,
            "embedding_dimension": env_settings.embedding_dimension,
            "vector_similarity_threshold": env_settings.vector_similarity_threshold,
        }
    
    def invalidate_cache(self):
        """Invalidate cached settings to force refresh from database."""
        self._cached_settings = None


# Global settings service instance
_settings_service: Optional[SettingsService] = None


def get_settings_service(db_manager: Optional[DatabaseManager] = None) -> SettingsService:
    """Get or create the global settings service instance."""
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService(db_manager)
    elif db_manager is not None and _settings_service.db_manager is None:
        _settings_service.db_manager = db_manager
    return _settings_service

