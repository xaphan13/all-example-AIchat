"""
Settings models for storing application configuration in the database.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class AppSettings(Base):
    """
    Stores application-wide settings including API keys.
    Typically only one row exists, acting as a singleton.
    """
    __tablename__ = "app_settings"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # API Keys (encrypted in production)
    openrouter_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Server Configuration
    backend_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    max_concurrent_agents: Mapped[int] = mapped_column(Integer, default=5)
    agent_timeout: Mapped[int] = mapped_column(Integer, default=120)
    
    # Database Configuration
    embedding_model: Mapped[str] = mapped_column(String(100), default="text-embedding-3-small")
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=1536)
    vector_similarity_threshold: Mapped[float] = mapped_column(default=0.7)
    
    # UI Preferences
    theme: Mapped[str] = mapped_column(String(20), default="system")
    enable_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_show_agent_panel: Mapped[bool] = mapped_column(Boolean, default=True)
    log_level: Mapped[str] = mapped_column(String(20), default="info")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    
    def __repr__(self):
        return f"<AppSettings(id={self.id}, updated_at={self.updated_at})>"

