"""
Repository layer for database operations.
Provides high-level interface for CRUD operations on conversations, messages, and embeddings.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Conversation, Message, Embedding
from ...core.config import settings


class ConversationRepository:
    """Repository for conversation operations."""
    
    @staticmethod
    async def create(
        session: AsyncSession,
        title: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            title=title,
            task_id=task_id,
            metadata_=metadata or {},
        )
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)
        return conversation
    
    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        include_messages: bool = False,
    ) -> Optional[Conversation]:
        """Get conversation by ID."""
        query = select(Conversation).where(Conversation.id == conversation_id)
        
        if include_messages:
            query = query.options(selectinload(Conversation.messages))
        
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_task_id(
        session: AsyncSession,
        task_id: str,
        include_messages: bool = False,
    ) -> List[Conversation]:
        """Get all conversations for a task."""
        query = select(Conversation).where(Conversation.task_id == task_id)
        
        if include_messages:
            query = query.options(selectinload(Conversation.messages))
        
        query = query.order_by(desc(Conversation.created_at))
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def list_recent(
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Conversation], int]:
        """List recent conversations with pagination."""
        # Get total count
        count_query = select(func.count(Conversation.id))
        count_result = await session.execute(count_query)
        total_count = count_result.scalar_one()
        
        # Get conversations
        query = (
            select(Conversation)
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        
        result = await session.execute(query)
        conversations = list(result.scalars().all())
        
        return conversations, total_count
    
    @staticmethod
    async def update(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        title: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Conversation]:
        """Update conversation."""
        conversation = await ConversationRepository.get_by_id(session, conversation_id)
        
        if conversation is None:
            return None
        
        if title is not None:
            conversation.title = title
        
        if metadata is not None:
            conversation.metadata_ = metadata
        
        conversation.updated_at = datetime.utcnow()
        
        await session.flush()
        await session.refresh(conversation)
        return conversation
    
    @staticmethod
    async def delete(session: AsyncSession, conversation_id: uuid.UUID) -> bool:
        """Delete conversation and all related data."""
        conversation = await ConversationRepository.get_by_id(session, conversation_id)
        
        if conversation is None:
            return False
        
        await session.delete(conversation)
        await session.flush()
        return True


class MessageRepository:
    """Repository for message operations."""
    
    @staticmethod
    async def create(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        agent_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        sequence_number: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_cost: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> Message:
        """Create a new message."""
        if sequence_number is None:
            # Get the next sequence number
            query = select(func.max(Message.sequence_number)).where(
                Message.conversation_id == conversation_id
            )
            result = await session.execute(query)
            max_seq = result.scalar_one_or_none()
            sequence_number = (max_seq or 0) + 1
        
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent_id=agent_id,
            agent_type=agent_type,
            sequence_number=sequence_number,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            total_cost=total_cost or 0.0,
            metadata_=metadata or {},
        )
        
        session.add(message)
        await session.flush()
        await session.refresh(message)
        return message
    
    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        message_id: uuid.UUID,
    ) -> Optional[Message]:
        """Get message by ID."""
        query = select(Message).where(Message.id == message_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_conversation(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """Get all messages in a conversation."""
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sequence_number)
        )
        
        if limit is not None:
            query = query.limit(limit)
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_agent(
        session: AsyncSession,
        agent_id: str,
        limit: int = 100,
    ) -> List[Message]:
        """Get all messages from a specific agent."""
        query = (
            select(Message)
            .where(Message.agent_id == agent_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        
        result = await session.execute(query)
        return list(result.scalars().all())


class EmbeddingRepository:
    """Repository for embedding operations and vector search."""
    
    @staticmethod
    async def create(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        embedding: List[float],
        text_content: str,
        model: str,
        message_id: Optional[uuid.UUID] = None,
        metadata: Optional[dict] = None,
    ) -> Embedding:
        """Create a new embedding."""
        embedding_obj = Embedding(
            conversation_id=conversation_id,
            message_id=message_id,
            embedding=embedding,
            text_content=text_content,
            model=model,
            metadata_=metadata or {},
        )
        
        session.add(embedding_obj)
        await session.flush()
        await session.refresh(embedding_obj)
        return embedding_obj
    
    @staticmethod
    async def get_by_message(
        session: AsyncSession,
        message_id: uuid.UUID,
    ) -> Optional[Embedding]:
        """Get embedding for a message."""
        query = select(Embedding).where(Embedding.message_id == message_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def similarity_search(
        session: AsyncSession,
        query_embedding: List[float],
        limit: int = 10,
        threshold: Optional[float] = None,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> List[Tuple[Embedding, float]]:
        """
        Perform similarity search using cosine distance.
        Returns embeddings with their similarity scores.
        
        Args:
            query_embedding: The query vector
            limit: Maximum number of results
            threshold: Minimum similarity threshold (0-1)
            conversation_id: Optional filter by conversation
        
        Returns:
            List of (Embedding, similarity_score) tuples, ordered by similarity
        """
        threshold = threshold or settings.vector_similarity_threshold
        
        # Calculate cosine similarity (1 - cosine_distance)
        # pgvector's <=> operator returns cosine distance
        similarity = 1 - Embedding.embedding.cosine_distance(query_embedding)
        
        query = (
            select(Embedding, similarity.label("similarity"))
            .where(similarity >= threshold)
        )
        
        if conversation_id is not None:
            query = query.where(Embedding.conversation_id == conversation_id)
        
        query = query.order_by(desc("similarity")).limit(limit)
        
        result = await session.execute(query)
        rows = result.all()
        
        return [(row[0], row[1]) for row in rows]
    
    @staticmethod
    async def search_conversations(
        session: AsyncSession,
        query_embedding: List[float],
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Tuple[Conversation, float]]:
        """
        Search for similar conversations based on embeddings.
        Returns unique conversations ordered by best match.
        """
        threshold = threshold or settings.vector_similarity_threshold
        
        similarity = 1 - Embedding.embedding.cosine_distance(query_embedding)
        
        # Get best match per conversation
        subquery = (
            select(
                Embedding.conversation_id,
                func.max(similarity).label("max_similarity")
            )
            .where(similarity >= threshold)
            .group_by(Embedding.conversation_id)
            .subquery()
        )
        
        query = (
            select(Conversation, subquery.c.max_similarity)
            .join(subquery, Conversation.id == subquery.c.conversation_id)
            .order_by(desc("max_similarity"))
            .limit(limit)
        )
        
        result = await session.execute(query)
        rows = result.all()
        
        return [(row[0], row[1]) for row in rows]
    
    @staticmethod
    async def get_by_conversation(
        session: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> List[Embedding]:
        """Get all embeddings for a conversation."""
        query = (
            select(Embedding)
            .where(Embedding.conversation_id == conversation_id)
            .order_by(Embedding.created_at)
        )
        
        result = await session.execute(query)
        return list(result.scalars().all())

