"""
Task processing endpoints (streaming and non-streaming).
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.core.models import TaskRequest
from src.core.orchestrator.task_orchestrator import TaskOrchestrator
from src.infrastructure.tracking.token_manager import get_token_manager
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["tasks"])


async def event_generator(task: TaskRequest, session_id: str) -> AsyncGenerator[str, None]:
    """
    Generate Server-Sent Events for task processing.
    
    Args:
        task: The task to process
        session_id: Session ID for token tracking
        
    Yields:
        SSE-formatted event strings
    """
    token_manager = get_token_manager()
    orchestrator = TaskOrchestrator(session_id=session_id)
    
    try:
        async for event_data in orchestrator.process_task(task):
            # Format as SSE
            event_json = json.dumps(event_data)
            yield f"data: {event_json}\n\n"
            
            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.01)
            
    except Exception as e:
        logger.error(
            "task_processing_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        error_event = {
            "type": "error",
            "error": str(e),
            "message": "An error occurred during task processing"
        }
        yield f"data: {json.dumps(error_event)}\n\n"
    finally:
        # Close session and log statistics
        await token_manager.close_session(session_id)
        session_stats = await token_manager.get_session_summary(session_id)
        if session_stats:
            logger.info(
                "session_token_usage_summary",
                session_id=session_id,
                total_cost=session_stats.get("total_cost", 0),
                total_tokens=session_stats.get("total_tokens", 0),
                total_requests=session_stats.get("total_requests", 0),
                duration_seconds=session_stats.get("duration_seconds", 0),
                usage_by_model=session_stats.get("usage_by_model", {}),
                usage_by_agent=session_stats.get("usage_by_agent", {})
            )
        
        # Always send a completion event to ensure the stream closes properly
        completion_event = {
            "type": "stream_end",
            "timestamp": datetime.now().isoformat()
        }
        yield f"data: {json.dumps(completion_event)}\n\n"


@router.post("/task/stream")
async def process_task_stream(task: TaskRequest):
    """
    Process a task with streaming responses via Server-Sent Events.
    
    Args:
        task: The task request
        
    Returns:
        EventSourceResponse with streaming updates
    """
    if not task.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Create a session for this request
    session_id = f"session_rest_{uuid.uuid4().hex[:12]}"
    token_manager = get_token_manager()
    await token_manager.create_session(session_id)
    
    logger.info(
        "task_stream_started",
        conversation_id=task.conversation_id,
        session_id=session_id,
        enable_collaboration=task.enable_collaboration,
        max_sub_agents=task.max_sub_agents,
        message_length=len(task.message)
    )
    
    return EventSourceResponse(
        event_generator(task, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/task")
async def process_task(task: TaskRequest):
    """
    Process a task and return the complete result (non-streaming).
    
    Args:
        task: The task request
        
    Returns:
        Complete task response
    """
    if not task.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Create a session for this request
    session_id = f"session_rest_{uuid.uuid4().hex[:12]}"
    token_manager = get_token_manager()
    await token_manager.create_session(session_id)
    orchestrator = TaskOrchestrator(session_id=session_id)
    
    logger.info(
        "task_processing_started",
        conversation_id=task.conversation_id,
        session_id=session_id,
        enable_collaboration=task.enable_collaboration,
        max_sub_agents=task.max_sub_agents,
        message_length=len(task.message)
    )
    
    try:
        events = []
        async for event_data in orchestrator.process_task(task):
            events.append(event_data)
        
        # Extract key information
        final_response = ""
        sub_agent_responses = []
        
        for event in events:
            if event.get("type") == "stream" and not event.get("isFinal"):
                final_response += event.get("content", "")
            elif event.get("type") == "sub_agent_response":
                sub_agent_responses.append({
                    "agentType": event.get("agentType"),
                    "content": event.get("content")
                })
        
        return {
            "conversationId": orchestrator.conversation_id,
            "finalResponse": final_response,
            "subAgentResponses": sub_agent_responses,
            "events": events
        }
    finally:
        # Close session and log statistics
        await token_manager.close_session(session_id)
        session_stats = await token_manager.get_session_summary(session_id)
        if session_stats:
            logger.info(
                "session_token_usage_summary",
                session_id=session_id,
                total_cost=session_stats.get("total_cost", 0),
                total_tokens=session_stats.get("total_tokens", 0),
                total_requests=session_stats.get("total_requests", 0),
                duration_seconds=session_stats.get("duration_seconds", 0),
                usage_by_model=session_stats.get("usage_by_model", {}),
                usage_by_agent=session_stats.get("usage_by_agent", {})
            )


@router.post("/reset")
async def reset_conversation():
    """
    Reset the conversation state.
    Note: With session-based tracking, each request gets its own orchestrator instance.
    This endpoint is kept for backwards compatibility.
    """
    logger.info("conversation_reset_requested")
    logger.info("conversation_reset_completed")
    return {"status": "success", "message": "Conversation reset"}

