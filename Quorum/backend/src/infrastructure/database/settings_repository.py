"""
Repository for managing application settings in the database.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from .settings_models import AppSettings
from ...core.config import settings as env_settings


class SettingsRepository:
    """Repository for application settings operations."""
    
    @staticmethod
    async def get_or_create(session: AsyncSession) -> AppSettings:
        """
        Get the application settings, or create default settings if none exist.
        This ensures a singleton pattern for settings.
        """
        # Try to get existing settings
        query = select(AppSettings).limit(1)
        result = await session.execute(query)
        app_settings = result.scalar_one_or_none()
        
        if app_settings is None:
            # Create default settings from environment variables
            app_settings = AppSettings(
                openrouter_api_key=env_settings.openrouter_api_key or "",
                backend_url=f"http://{env_settings.host}:{env_settings.port}",
                max_concurrent_agents=env_settings.max_concurrent_agents,
                agent_timeout=env_settings.agent_timeout,
                embedding_model=env_settings.embedding_model,
                embedding_dimension=env_settings.embedding_dimension,
                vector_similarity_threshold=env_settings.vector_similarity_threshold,
                theme="system",
                enable_notifications=True,
                auto_show_agent_panel=True,
                log_level=env_settings.log_level.lower(),
            )
            session.add(app_settings)
            await session.flush()
            await session.refresh(app_settings)
        
        return app_settings
    
    @staticmethod
    async def get(session: AsyncSession) -> Optional[AppSettings]:
        """Get the application settings."""
        query = select(AppSettings).limit(1)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update(
        session: AsyncSession,
        openrouter_api_key: Optional[str] = None,
        backend_url: Optional[str] = None,
        max_concurrent_agents: Optional[int] = None,
        agent_timeout: Optional[int] = None,
        embedding_model: Optional[str] = None,
        embedding_dimension: Optional[int] = None,
        vector_similarity_threshold: Optional[float] = None,
        theme: Optional[str] = None,
        enable_notifications: Optional[bool] = None,
        auto_show_agent_panel: Optional[bool] = None,
        log_level: Optional[str] = None,
    ) -> AppSettings:
        """Update application settings."""
        app_settings = await SettingsRepository.get_or_create(session)
        
        # Update fields if provided
        if openrouter_api_key is not None:
            app_settings.openrouter_api_key = openrouter_api_key
        if backend_url is not None:
            app_settings.backend_url = backend_url
        if max_concurrent_agents is not None:
            app_settings.max_concurrent_agents = max_concurrent_agents
        if agent_timeout is not None:
            app_settings.agent_timeout = agent_timeout
        if embedding_model is not None:
            app_settings.embedding_model = embedding_model
        if embedding_dimension is not None:
            app_settings.embedding_dimension = embedding_dimension
        if vector_similarity_threshold is not None:
            app_settings.vector_similarity_threshold = vector_similarity_threshold
        if theme is not None:
            app_settings.theme = theme
        if enable_notifications is not None:
            app_settings.enable_notifications = enable_notifications
        if auto_show_agent_panel is not None:
            app_settings.auto_show_agent_panel = auto_show_agent_panel
        if log_level is not None:
            app_settings.log_level = log_level
        
        app_settings.updated_at = datetime.utcnow()
        
        await session.flush()
        await session.refresh(app_settings)
        return app_settings
    
    @staticmethod
    def to_dict(app_settings: AppSettings, include_api_keys: bool = True) -> dict:
        """
        Convert settings to dictionary.
        
        Args:
            app_settings: The settings object
            include_api_keys: Whether to include API keys (masked by default)
        """
        data = {
            "id": str(app_settings.id),
            "backend_url": app_settings.backend_url,
            "max_concurrent_agents": app_settings.max_concurrent_agents,
            "agent_timeout": app_settings.agent_timeout,
            "embedding_model": app_settings.embedding_model,
            "embedding_dimension": app_settings.embedding_dimension,
            "vector_similarity_threshold": app_settings.vector_similarity_threshold,
            "theme": app_settings.theme,
            "enable_notifications": app_settings.enable_notifications,
            "auto_show_agent_panel": app_settings.auto_show_agent_panel,
            "log_level": app_settings.log_level,
            "created_at": app_settings.created_at.isoformat(),
            "updated_at": app_settings.updated_at.isoformat(),
        }
        
        if include_api_keys:
            # Mask API keys for security (show only first/last few chars)
            data["openrouter_api_key"] = _mask_api_key(app_settings.openrouter_api_key)
        else:
            data["openrouter_api_key"] = app_settings.openrouter_api_key
        
        return data


def _mask_api_key(api_key: Optional[str]) -> str:
    """Mask an API key for display."""
    if not api_key:
        return ""
    
    if len(api_key) < 12:
        return "***"
    
    return f"{api_key[:6]}...{api_key[-4:]}"

