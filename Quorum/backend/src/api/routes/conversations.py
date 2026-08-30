"""
API endpoints for conversation management.
Allows retrieving, listing, and managing conversation history.
"""
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from src.infrastructure.database import (
    get_db,
    ConversationRepository,
    MessageRepository,
    ConversationService,
)
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


# Response models
class MessageResponse(BaseModel):
    """Response model for a message."""
    id: str
    conversation_id: str
    role: str
    content: str
    agent_id: Optional[str] = None
    agent_type: Optional[str] = None
    sequence_number: int
    created_at: datetime
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    total_cost: Optional[float] = 0.0
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Response model for a conversation."""
    id: str
    title: Optional[str] = None
    task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    metadata: Optional[dict] = None
    message_count: Optional[int] = None
    messages: Optional[List[MessageResponse]] = None

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Response model for paginated conversation list."""
    conversations: List[ConversationResponse]
    total: int
    limit: int
    offset: int


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(50, ge=1, le=100, description="Number of conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    db: AsyncSession = Depends(get_db),
):
    """
    List recent conversations with pagination.
    
    Args:
        limit: Number of conversations to return (max 100)
        offset: Number of conversations to skip for pagination
        db: Database session
        
    Returns:
        Paginated list of conversations
    """
    try:
        conversations, total = await ConversationRepository.list_recent(
            db,
            limit=limit,
            offset=offset
        )
        
        # Convert to response models
        conversation_responses = []
        for conv in conversations:
            # Count messages for each conversation
            messages = await MessageRepository.get_by_conversation(db, conv.id)
            
            conversation_responses.append(
                ConversationResponse(
                    id=str(conv.id),
                    title=conv.title,
                    task_id=conv.task_id,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    metadata=conv.metadata_,
                    message_count=len(messages),
                    messages=None  # Don't include messages in list view
                )
            )
        
        logger.info(
            "conversations_listed",
            total=total,
            returned=len(conversation_responses),
            limit=limit,
            offset=offset
        )
        
        return ConversationListResponse(
            conversations=conversation_responses,
            total=total,
            limit=limit,
            offset=offset
        )
    
    except Exception as e:
        logger.error(
            "list_conversations_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    include_messages: bool = Query(True, description="Include messages in response"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific conversation by ID.
    
    Args:
        conversation_id: UUID of the conversation
        include_messages: Whether to include messages in the response
        db: Database session
        
    Returns:
        Conversation with optional messages
    """
    try:
        # Parse UUID
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
        # Get conversation
        conversation = await ConversationRepository.get_by_id(
            db,
            conv_uuid,
            include_messages=include_messages
        )
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages if requested
        messages = None
        if include_messages:
            db_messages = await MessageRepository.get_by_conversation(db, conv_uuid)
            messages = [
                MessageResponse(
                    id=str(msg.id),
                    conversation_id=str(msg.conversation_id),
                    role=msg.role,
                    content=msg.content,
                    agent_id=msg.agent_id,
                    agent_type=msg.agent_type,
                    sequence_number=msg.sequence_number,
                    created_at=msg.created_at,
                    input_tokens=msg.input_tokens,
                    output_tokens=msg.output_tokens,
                    total_cost=msg.total_cost,
                    metadata=msg.metadata_
                )
                for msg in db_messages
            ]
        
        logger.info(
            "conversation_retrieved",
            conversation_id=conversation_id,
            include_messages=include_messages,
            message_count=len(messages) if messages else 0
        )
        
        return ConversationResponse(
            id=str(conversation.id),
            title=conversation.title,
            task_id=conversation.task_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=conversation.metadata_,
            message_count=len(messages) if messages else None,
            messages=messages
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_conversation_error",
            conversation_id=conversation_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}", response_model=List[ConversationResponse])
async def get_conversations_by_task(
    task_id: str,
    include_messages: bool = Query(False, description="Include messages in response"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all conversations for a specific task ID.
    
    Args:
        task_id: Task identifier
        include_messages: Whether to include messages in the response
        db: Database session
        
    Returns:
        List of conversations for the task
    """
    try:
        conversations = await ConversationRepository.get_by_task_id(
            db,
            task_id,
            include_messages=include_messages
        )
        
        conversation_responses = []
        for conv in conversations:
            messages = None
            message_count = 0
            
            if include_messages:
                db_messages = await MessageRepository.get_by_conversation(db, conv.id)
                message_count = len(db_messages)
                messages = [
                    MessageResponse(
                        id=str(msg.id),
                        conversation_id=str(msg.conversation_id),
                        role=msg.role,
                        content=msg.content,
                        agent_id=msg.agent_id,
                        agent_type=msg.agent_type,
                        sequence_number=msg.sequence_number,
                        created_at=msg.created_at,
                        input_tokens=msg.input_tokens,
                        output_tokens=msg.output_tokens,
                        total_cost=msg.total_cost,
                        metadata=msg.metadata_
                    )
                    for msg in db_messages
                ]
            else:
                db_messages = await MessageRepository.get_by_conversation(db, conv.id)
                message_count = len(db_messages)
            
            conversation_responses.append(
                ConversationResponse(
                    id=str(conv.id),
                    title=conv.title,
                    task_id=conv.task_id,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    metadata=conv.metadata_,
                    message_count=message_count,
                    messages=messages
                )
            )
        
        logger.info(
            "conversations_by_task_retrieved",
            task_id=task_id,
            count=len(conversation_responses),
            include_messages=include_messages
        )
        
        return conversation_responses
    
    except Exception as e:
        logger.error(
            "get_conversations_by_task_error",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a conversation and all its messages.
    
    Args:
        conversation_id: UUID of the conversation to delete
        db: Database session
        
    Returns:
        Success message
    """
    try:
        # Parse UUID
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
        # Delete conversation
        success = await ConversationRepository.delete(db, conv_uuid)
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        logger.info(
            "conversation_deleted",
            conversation_id=conversation_id
        )
        
        return {"success": True, "message": "Conversation deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "delete_conversation_error",
            conversation_id=conversation_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


class UpdateConversationRequest(BaseModel):
    """Request model for updating a conversation."""
    title: Optional[str] = Field(None, description="New title for the conversation")


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    update: UpdateConversationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a conversation's metadata.
    
    Args:
        conversation_id: UUID of the conversation to update
        update: Update request with new values
        db: Database session
        
    Returns:
        Updated conversation
    """
    try:
        # Parse UUID
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
        # Update conversation
        conversation = await ConversationRepository.update(
            db,
            conv_uuid,
            title=update.title
        )
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get message count
        messages = await MessageRepository.get_by_conversation(db, conv_uuid)
        
        logger.info(
            "conversation_updated",
            conversation_id=conversation_id,
            title=update.title
        )
        
        return ConversationResponse(
            id=str(conversation.id),
            title=conversation.title,
            task_id=conversation.task_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=conversation.metadata_,
            message_count=len(messages),
            messages=None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_conversation_error",
            conversation_id=conversation_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

