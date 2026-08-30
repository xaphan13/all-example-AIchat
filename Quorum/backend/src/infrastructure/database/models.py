"""
SQLAlchemy models for conversations, messages, and embeddings.
Uses pgvector for storing and searching vector embeddings.
"""
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from ...core.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Conversation(Base):
    """
    Stores conversation metadata.
    Each conversation contains multiple messages.
    """
    __tablename__ = "conversations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Conversation metadata
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    
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
    
    # Metadata stored as JSONB for flexible querying
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
    )
    
    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    
    embeddings: Mapped[List["Embedding"]] = relationship(
        "Embedding",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title}, created_at={self.created_at})>"


class Message(Base):
    """
    Stores individual messages within a conversation.
    Messages can be from user, assistant, or system.
    """
    __tablename__ = "messages"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Message content
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Optional agent information
    agent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    agent_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Message sequence
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    # Token usage tracking
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    total_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    
    # Additional metadata
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
    )
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    
    embedding: Mapped[Optional["Embedding"]] = relationship(
        "Embedding",
        back_populates="message",
        uselist=False,
        cascade="all, delete-orphan",
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"


class Embedding(Base):
    """
    Stores vector embeddings for messages to enable semantic search.
    Uses pgvector extension for efficient similarity search.
    """
    __tablename__ = "embeddings"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
    
    # Vector embedding
    embedding: Mapped[List[float]] = mapped_column(
        Vector(settings.embedding_dimension),
        nullable=False,
    )
    
    # Embedding metadata
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    # Additional metadata
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
    )
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="embeddings",
    )
    
    message: Mapped[Optional["Message"]] = relationship(
        "Message",
        back_populates="embedding",
    )
    
    def __repr__(self):
        return f"<Embedding(id={self.id}, model={self.model}, conversation_id={self.conversation_id})>"


# Create indexes for better query performance
Index("idx_messages_conversation_sequence", Message.conversation_id, Message.sequence_number)
Index("idx_messages_created_at", Message.created_at)
Index("idx_conversations_created_at", Conversation.created_at)
Index("idx_embeddings_conversation", Embedding.conversation_id)

# Create vector similarity index for efficient nearest neighbor search
# This uses the IVFFlat or HNSW index for fast vector search
Index(
    "idx_embeddings_vector",
    Embedding.embedding,
    postgresql_using="ivfflat",
    postgresql_with={"lists": 100},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)

