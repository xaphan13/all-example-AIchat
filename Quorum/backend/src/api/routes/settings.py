"""
Settings management API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import get_db, SettingsRepository
from src.infrastructure.logging.config import get_logger
from src.core.settings_service import get_settings_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    """Request model for updating settings."""
    openrouter_api_key: Optional[str] = None
    backend_url: Optional[str] = None
    max_concurrent_agents: Optional[int] = None
    agent_timeout: Optional[int] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    vector_similarity_threshold: Optional[float] = None
    theme: Optional[str] = None
    enable_notifications: Optional[bool] = None
    auto_show_agent_panel: Optional[bool] = None
    log_level: Optional[str] = None


class SettingsResponse(BaseModel):
    """Response model for settings."""
    id: str
    openrouter_api_key: str
    backend_url: Optional[str]
    max_concurrent_agents: int
    agent_timeout: int
    embedding_model: str
    embedding_dimension: int
    vector_similarity_threshold: float
    theme: str
    enable_notifications: bool
    auto_show_agent_panel: bool
    log_level: str
    created_at: str
    updated_at: str


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    mask_keys: bool = True,
):
    """
    Get application settings.
    
    Query Parameters:
        mask_keys: Whether to mask API keys (default: true)
    """
    try:
        logger.info("get_settings_requested", mask_keys=mask_keys)
        
        app_settings = await SettingsRepository.get_or_create(db)
        settings_dict = SettingsRepository.to_dict(app_settings, include_api_keys=True)
        
        # If mask_keys is False, return full API keys (for authenticated requests only)
        if not mask_keys:
            settings_dict["openrouter_api_key"] = app_settings.openrouter_api_key or ""
        
        logger.info("get_settings_success")
        return settings_dict
        
    except Exception as e:
        logger.error("get_settings_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve settings")


@router.put("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update application settings."""
    try:
        logger.info("update_settings_requested", fields=list(request.model_dump(exclude_none=True).keys()))
        
        # Filter out None values
        update_data = request.model_dump(exclude_none=True)
        
        app_settings = await SettingsRepository.update(db, **update_data)
        settings_dict = SettingsRepository.to_dict(app_settings, include_api_keys=True)
        
        # Invalidate settings service cache so agents get new API keys
        settings_service = get_settings_service()
        settings_service.invalidate_cache()
        logger.info("settings_cache_invalidated")
        
        logger.info("update_settings_success")
        return settings_dict
        
    except Exception as e:
        logger.error("update_settings_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/api-keys/validate")
async def validate_api_keys(db: AsyncSession = Depends(get_db)):
    """
    Validate that API keys are configured.
    Returns which keys are present (not the actual keys).
    """
    try:
        app_settings = await SettingsRepository.get_or_create(db)
        
        validation = {
            "openrouter": bool(app_settings.openrouter_api_key and len(app_settings.openrouter_api_key) > 10),
        }
        
        return {
            "configured": validation,
            "all_configured": all(validation.values()),
        }
        
    except Exception as e:
        logger.error("validate_api_keys_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate API keys")

