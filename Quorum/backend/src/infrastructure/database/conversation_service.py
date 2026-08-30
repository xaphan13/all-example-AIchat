"""
Service for managing conversation persistence.
Handles creating conversations and saving messages with proper tracking.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import ConversationRepository, MessageRepository
from .models import Conversation, Message
from ...infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class ConversationService:
    """Service for conversation persistence operations."""
    
    @staticmethod
    async def get_or_create_conversation(
        session: AsyncSession,
        conversation_id: Optional[str] = None,
        title: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Conversation:
        """
        Get an existing conversation or create a new one.
        
        Args:
            session: Database session
            conversation_id: Optional existing conversation ID (string format like "conv_abc123")
            title: Optional title for the conversation
            task_id: Optional task ID for tracking
            metadata: Optional metadata dictionary
            
        Returns:
            Conversation object
        """
        # If conversation_id provided, try to get it
        if conversation_id:
            try:
                # Convert string ID to UUID if needed
                if conversation_id.startswith("conv_"):
                    # This is a generated ID, check if it exists in DB
                    # Search by task_id instead
                    if task_id:
                        conversations = await ConversationRepository.get_by_task_id(session, task_id)
                        if conversations:
                            logger.debug(
                                "conversation_found_by_task_id",
                                conversation_id=str(conversations[0].id),
                                task_id=task_id
                            )
                            return conversations[0]
                else:
                    # Assume it's a UUID
                    conv_uuid = uuid.UUID(conversation_id)
                    existing = await ConversationRepository.get_by_id(session, conv_uuid)
                    if existing:
                        logger.debug(
                            "conversation_found",
                            conversation_id=str(existing.id)
                        )
                        return existing
            except (ValueError, AttributeError) as e:
                logger.warning(
                    "invalid_conversation_id_format",
                    conversation_id=conversation_id,
                    error=str(e)
                )
        
        # Create new conversation
        new_conversation = await ConversationRepository.create(
            session,
            title=title,
            task_id=task_id or conversation_id,
            metadata=metadata or {}
        )
        
        logger.info(
            "conversation_created",
            conversation_id=str(new_conversation.id),
            task_id=task_id or conversation_id
        )
        
        return new_conversation
    
    @staticmethod
    async def save_user_message(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Message:
        """
        Save a user message to the database.
        
        Args:
            session: Database session
            conversation_id: Conversation UUID
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Created Message object
        """
        message = await MessageRepository.create(
            session,
            conversation_id=conversation_id,
            role="user",
            content=content,
            metadata=metadata
        )
        
        logger.info(
            "user_message_saved",
            message_id=str(message.id),
            conversation_id=str(conversation_id),
            content_length=len(content)
        )
        
        return message
    
    @staticmethod
    async def save_assistant_message(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        content: str,
        agent_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_cost: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> Message:
        """
        Save an assistant message to the database.
        
        Args:
            session: Database session
            conversation_id: Conversation UUID
            content: Message content
            agent_id: Optional agent identifier
            agent_type: Optional agent type
            input_tokens: Optional input token count
            output_tokens: Optional output token count
            total_cost: Optional total cost
            metadata: Optional metadata
            
        Returns:
            Created Message object
        """
        message = await MessageRepository.create(
            session,
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            agent_id=agent_id,
            agent_type=agent_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            metadata=metadata
        )
        
        logger.info(
            "assistant_message_saved",
            message_id=str(message.id),
            conversation_id=str(conversation_id),
            agent_id=agent_id,
            agent_type=agent_type,
            content_length=len(content),
            tokens={"input": input_tokens, "output": output_tokens},
            cost=total_cost
        )
        
        return message
    
    @staticmethod
    async def save_agent_conversation_message(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        content: str,
        agent_id: str,
        agent_type: str,
        round_number: int,
        metadata: Optional[dict] = None,
    ) -> Message:
        """
        Save an agent-to-agent conversation message.
        
        Args:
            session: Database session
            conversation_id: Conversation UUID
            content: Message content
            agent_id: Agent identifier
            agent_type: Agent type
            round_number: Conversation round number
            metadata: Optional metadata
            
        Returns:
            Created Message object
        """
        # Enhance metadata with round info
        enhanced_metadata = metadata or {}
        enhanced_metadata["round_number"] = round_number
        enhanced_metadata["message_type"] = "agent_conversation"
        
        message = await MessageRepository.create(
            session,
            conversation_id=conversation_id,
            role="assistant",  # Agent messages are assistant-type
            content=content,
            agent_id=agent_id,
            agent_type=agent_type,
            metadata=enhanced_metadata
        )
        
        logger.info(
            "agent_conversation_message_saved",
            message_id=str(message.id),
            conversation_id=str(conversation_id),
            agent_id=agent_id,
            agent_type=agent_type,
            round_number=round_number
        )
        
        return message
    
    @staticmethod
    async def update_conversation_title(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        title: str,
    ) -> Optional[Conversation]:
        """
        Update conversation title.
        
        Args:
            session: Database session
            conversation_id: Conversation UUID
            title: New title
            
        Returns:
            Updated Conversation object or None
        """
        conversation = await ConversationRepository.update(
            session,
            conversation_id=conversation_id,
            title=title
        )
        
        if conversation:
            logger.info(
                "conversation_title_updated",
                conversation_id=str(conversation_id),
                title=title
            )
        
        return conversation
    
    @staticmethod
    async def get_conversation_with_messages(
        session: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> Optional[Conversation]:
        """
        Get a conversation with all its messages loaded.
        
        Args:
            session: Database session
            conversation_id: Conversation UUID
            
        Returns:
            Conversation with messages or None
        """
        conversation = await ConversationRepository.get_by_id(
            session,
            conversation_id,
            include_messages=True
        )
        
        if conversation:
            logger.debug(
                "conversation_retrieved",
                conversation_id=str(conversation_id),
                message_count=len(conversation.messages)
            )
        
        return conversation

