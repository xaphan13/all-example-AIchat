"""
Configuration management for the multi-agent system.
Loads environment variables and provides typed configuration access.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from dotenv import dotenv_values


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Keys
    openrouter_api_key: str = ""
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    use_redis: bool = False
    
    # Agent Configuration
    max_concurrent_agents: int = 5
    agent_timeout: int = 120
    stream_chunk_size: int = 32
    
    # Logging Configuration
    log_level: str = "INFO"
    log_json: bool = False
    log_file: str = ""
    
    # Database Configuration
    database_url: str = "postgresql://quorum:quorum@localhost:5432/quorum"
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "quorum"
    database_user: str = "quorum"
    database_password: str = "quorum"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # Vector Store Configuration
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    vector_similarity_threshold: float = 0.7
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        validate_default=True
    )
    
    def __init__(self, **kwargs):
        """Initialize settings, prioritizing .env file over dummy environment variables."""
        super().__init__(**kwargs)
        
        # Load values directly from .env file
        env_file_path = Path(__file__).parent.parent.parent / ".env"
        if env_file_path.exists():
            env_values = dotenv_values(env_file_path)
            
            # Override if current values are dummy values or short placeholders
            if self.openrouter_api_key and len(self.openrouter_api_key) < 30:
                if 'OPENROUTER_API_KEY' in env_values and env_values['OPENROUTER_API_KEY']:
                    object.__setattr__(self, 'openrouter_api_key', env_values['OPENROUTER_API_KEY'])
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()

