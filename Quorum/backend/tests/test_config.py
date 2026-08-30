"""Tests for configuration management."""
import pytest
import os
from src.core.config import Settings


class TestSettings:
    """Test Settings configuration."""
    
    def test_settings_defaults(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.max_concurrent_agents == 5
        assert settings.agent_timeout == 120
        assert settings.stream_chunk_size == 32
        assert settings.use_redis is False
    
    def test_settings_from_env(self):
        """Test settings load from environment."""
        # Environment is already set in conftest.py
        settings = Settings()
        assert settings.openrouter_api_key == "test-key-openrouter"
    
    def test_cors_origins_list(self):
        """Test CORS origins parsing."""
        settings = Settings()
        origins = settings.cors_origins_list
        assert isinstance(origins, list)
        assert len(origins) == 2
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins
    
    def test_redis_config(self):
        """Test Redis configuration."""
        settings = Settings()
        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.redis_db == 0

