"""Database infrastructure module."""
from .connection import DatabaseManager, get_db, db_manager
from .models import Base, Conversation, Message, Embedding
from .settings_models import AppSettings
from .repository import ConversationRepository, MessageRepository, EmbeddingRepository
from .settings_repository import SettingsRepository
from .vector_service import VectorService
from .conversation_service import ConversationService

__all__ = [
    "DatabaseManager",
    "db_manager",
    "get_db",
    "Base",
    "Conversation",
    "Message",
    "Embedding",
    "AppSettings",
    "ConversationRepository",
    "MessageRepository",
    "EmbeddingRepository",
    "SettingsRepository",
    "VectorService",
    "ConversationService",
]

