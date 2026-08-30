"""
WebSocket endpoint for real-time bidirectional communication.
"""
from datetime import datetime
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.core.models import WebSocketMessage
from src.core.orchestrator.task_orchestrator import TaskOrchestrator
from src.infrastructure.websocket.manager import connection_manager
from src.infrastructure.tracking.token_manager import get_token_manager
from src.infrastructure.logging.config import get_logger
from src.infrastructure.database import db_manager, ConversationService

logger = get_logger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time bidirectional communication.
    Supports task streaming, conversation subscriptions, and live updates.
    """
    connection_id = await connection_manager.connect(websocket)
    session_id = connection_manager.get_session_id(connection_id)
    
    # Initialize token tracking for this session
    token_manager = get_token_manager()
    if session_id:
        await token_manager.create_session(session_id)
    
    # Create a PERSISTENT orchestrator for this WebSocket connection
    # This ensures conversation context is maintained across multiple messages
    persistent_orchestrator = TaskOrchestrator(
        websocket_mode=True,
        connection_manager=connection_manager,
        session_id=session_id
    )
    
    # Track active orchestrators by conversation ID for this connection
    active_conversation_orchestrators = {}
    
    try:
        # Send welcome message
        await connection_manager.send_personal_message(
            {
                "type": "connected",
                "connectionId": connection_id,
                "sessionId": session_id,
                "timestamp": datetime.now().isoformat()
            },
            connection_id
        )
        
        logger.info("websocket_session_started", connection_id=connection_id, session_id=session_id)
        
        while True:
            # Receive message from client
            try:
                data = await websocket.receive_json()
            except RuntimeError as e:
                # Handle "WebSocket is not connected" error as a normal disconnect
                if "not connected" in str(e).lower():
                    logger.info(
                        "websocket_connection_closed_by_client",
                        connection_id=connection_id,
                        session_id=session_id
                    )
                    break  # Exit the loop gracefully
                raise  # Re-raise if it's a different RuntimeError
            
            try:
                # Parse as WebSocketMessage
                ws_message = WebSocketMessage(**data)
                
                logger.debug(
                    "websocket_message_received",
                    connection_id=connection_id,
                    message_type=ws_message.type
                )
                
                # Handle different message types
                if ws_message.type == "ping":
                    # Respond to ping with pong
                    await connection_manager.send_personal_message(
                        {
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        },
                        connection_id
                    )
                
                elif ws_message.type == "subscribe":
                    # Subscribe to a conversation
                    if ws_message.conversation_id:
                        connection_manager.subscribe_to_conversation(
                            connection_id,
                            ws_message.conversation_id
                        )
                        await connection_manager.send_personal_message(
                            {
                                "type": "subscribed",
                                "conversationId": ws_message.conversation_id,
                                "timestamp": datetime.now().isoformat()
                            },
                            connection_id
                        )
                
                elif ws_message.type == "unsubscribe":
                    # Unsubscribe from a conversation
                    if ws_message.conversation_id:
                        connection_manager.unsubscribe_from_conversation(
                            connection_id,
                            ws_message.conversation_id
                        )
                        await connection_manager.send_personal_message(
                            {
                                "type": "unsubscribed",
                                "conversationId": ws_message.conversation_id,
                                "timestamp": datetime.now().isoformat()
                            },
                            connection_id
                        )
                
                elif ws_message.type == "task":
                    # Process a task and stream results over WebSocket
                    if ws_message.task:
                        logger.info(
                            "websocket_task_started",
                            connection_id=connection_id,
                            conversation_id=ws_message.task.conversation_id
                        )
                        
                        # Create or get conversation in database
                        db_conversation = None
                        db_conversation_uuid = None
                        
                        try:
                            async with db_manager.session() as db_session:
                                db_conversation = await ConversationService.get_or_create_conversation(
                                    db_session,
                                    conversation_id=ws_message.task.conversation_id,
                                    title=None,  # Will be updated later if needed
                                    task_id=ws_message.task.conversation_id,
                                    metadata={
                                        "session_id": session_id,
                                        "connection_id": connection_id,
                                        "max_sub_agents": ws_message.task.max_sub_agents,
                                        "enable_collaboration": ws_message.task.enable_collaboration,
                                    }
                                )
                                db_conversation_uuid = db_conversation.id
                                
                                # Save user message to database
                                await ConversationService.save_user_message(
                                    db_session,
                                    conversation_id=db_conversation_uuid,
                                    content=ws_message.task.message,
                                    metadata={
                                        "timestamp": datetime.now().isoformat(),
                                        "session_id": session_id,
                                    }
                                )
                                
                                logger.info(
                                    "conversation_and_user_message_saved",
                                    db_conversation_id=str(db_conversation_uuid),
                                    task_conversation_id=ws_message.task.conversation_id
                                )
                        except Exception as e:
                            logger.error(
                                "failed_to_save_conversation_to_db",
                                error=str(e),
                                error_type=type(e).__name__,
                                exc_info=True
                            )
                        
                        # Get or create orchestrator for this conversation
                        # Reuse existing orchestrator to maintain conversation history in memory
                        conv_id = ws_message.task.conversation_id or f"conv_{connection_id}"
                        
                        if conv_id not in active_conversation_orchestrators:
                            # Create new orchestrator for this conversation
                            ws_orchestrator = TaskOrchestrator(
                                websocket_mode=True,
                                connection_manager=connection_manager,
                                session_id=session_id
                            )
                            active_conversation_orchestrators[conv_id] = ws_orchestrator
                            logger.info(
                                "created_new_orchestrator_for_conversation",
                                conversation_id=conv_id,
                                connection_id=connection_id
                            )
                        else:
                            # Reuse existing orchestrator for conversation continuity
                            ws_orchestrator = active_conversation_orchestrators[conv_id]
                            logger.info(
                                "reusing_existing_orchestrator",
                                conversation_id=conv_id,
                                connection_id=connection_id
                            )
                        
                        # Register the task so it can be cancelled
                        connection_manager.register_task(conv_id, ws_orchestrator)
                        
                        # Auto-subscribe the connection to this conversation to receive events
                        connection_manager.subscribe_to_conversation(connection_id, conv_id)
                        logger.debug(
                            "auto_subscribed_to_conversation",
                            connection_id=connection_id,
                            conversation_id=conv_id
                        )
                        
                        # Track streaming response and agent messages
                        accumulated_response = ""
                        agent_messages = []
                        actual_conv_id = conv_id  # Will be updated from init event
                        
                        try:
                            # Process task and stream events via WebSocket
                            async for event_data in ws_orchestrator.process_task(ws_message.task):
                                # Track important events for database storage
                                event_type = event_data.get("type")
                                
                                # On init event, get the actual conversation ID and resubscribe
                                if event_type == "init" and event_data.get("conversationId"):
                                    actual_conv_id = event_data["conversationId"]
                                    # Unsubscribe from old ID and subscribe to actual ID
                                    if actual_conv_id != conv_id:
                                        connection_manager.unsubscribe_from_conversation(connection_id, conv_id)
                                        connection_manager.subscribe_to_conversation(connection_id, actual_conv_id)
                                        # Also update task registration
                                        connection_manager.unregister_task(conv_id)
                                        connection_manager.register_task(actual_conv_id, ws_orchestrator)
                                        
                                        # CRITICAL: Update orchestrator dictionary key
                                        # Move orchestrator from old key to new key to maintain persistence
                                        if conv_id in active_conversation_orchestrators:
                                            active_conversation_orchestrators[actual_conv_id] = active_conversation_orchestrators.pop(conv_id)
                                            logger.info(
                                                "orchestrator_key_updated",
                                                connection_id=connection_id,
                                                old_key=conv_id,
                                                new_key=actual_conv_id
                                            )
                                        
                                        logger.info(
                                            "resubscribed_to_actual_conversation",
                                            connection_id=connection_id,
                                            old_conv_id=conv_id,
                                            new_conv_id=actual_conv_id
                                        )
                                
                                # Accumulate final response
                                if event_type == "stream":
                                    accumulated_response += event_data.get("content", "")
                                elif event_type == "complete":
                                    # Use the complete final response if provided
                                    if event_data.get("finalResponse"):
                                        accumulated_response = event_data["finalResponse"]
                                elif event_type == "agent_message" and event_data.get("isComplete"):
                                    # Track agent conversation messages
                                    agent_messages.append({
                                        "agent_id": event_data.get("agentId"),
                                        "agent_type": event_data.get("agentType"),
                                        "content": event_data.get("content"),
                                        "round_number": event_data.get("roundNumber"),
                                        "timestamp": event_data.get("timestamp"),
                                    })
                                
                                # Send event to subscribed clients (or just this connection)
                                # Use actual_conv_id (the real conversation ID from the orchestrator)
                                event_conv_id = event_data.get("conversationId") or actual_conv_id
                                
                                # Log complete event specifically
                                if event_type == "complete":
                                    logger.info(
                                        "broadcasting_complete_event",
                                        event_conv_id=event_conv_id,
                                        has_final_response=bool(event_data.get("finalResponse")),
                                        connection_id=connection_id,
                                        actual_conv_id=actual_conv_id
                                    )
                                
                                if event_conv_id:
                                    # Broadcast to all subscribers of this conversation
                                    await connection_manager.broadcast_to_conversation(
                                        event_data,
                                        event_conv_id
                                    )
                                else:
                                    # Send to requesting connection only
                                    await connection_manager.send_personal_message(
                                        event_data,
                                        connection_id
                                    )
                            
                            # Save accumulated response and agent messages to database
                            if db_conversation_uuid and accumulated_response:
                                try:
                                    async with db_manager.session() as db_session:
                                        # Save main assistant response
                                        await ConversationService.save_assistant_message(
                                            db_session,
                                            conversation_id=db_conversation_uuid,
                                            content=accumulated_response,
                                            agent_id="main_orchestrator",
                                            agent_type="claude-sonnet-4.5",
                                            metadata={
                                                "timestamp": datetime.now().isoformat(),
                                                "session_id": session_id,
                                            }
                                        )
                                        
                                        # Save agent conversation messages
                                        for agent_msg in agent_messages:
                                            await ConversationService.save_agent_conversation_message(
                                                db_session,
                                                conversation_id=db_conversation_uuid,
                                                content=agent_msg["content"],
                                                agent_id=agent_msg["agent_id"],
                                                agent_type=agent_msg["agent_type"],
                                                round_number=agent_msg["round_number"],
                                                metadata={
                                                    "timestamp": agent_msg["timestamp"],
                                                    "session_id": session_id,
                                                }
                                            )
                                        
                                        logger.info(
                                            "assistant_response_and_agent_messages_saved",
                                            db_conversation_id=str(db_conversation_uuid),
                                            response_length=len(accumulated_response),
                                            agent_message_count=len(agent_messages)
                                        )
                                except Exception as e:
                                    logger.error(
                                        "failed_to_save_assistant_response_to_db",
                                        error=str(e),
                                        error_type=type(e).__name__,
                                        exc_info=True
                                    )
                            
                            logger.info(
                                "websocket_task_completed",
                                connection_id=connection_id,
                                conversation_id=actual_conv_id
                            )
                        finally:
                            # Unregister the task when it's done (use actual_conv_id)
                            connection_manager.unregister_task(actual_conv_id)
                            # Unsubscribe from the conversation
                            connection_manager.unsubscribe_from_conversation(connection_id, actual_conv_id)
                            # NOTE: We do NOT remove the orchestrator from active_conversation_orchestrators
                            # It stays alive for the duration of the WebSocket connection to maintain conversation history
                
                elif ws_message.type == "stop":
                    # Stop/cancel an active task
                    if ws_message.conversation_id:
                        logger.info(
                            "stop_request_received",
                            connection_id=connection_id,
                            conversation_id=ws_message.conversation_id
                        )
                        
                        success = connection_manager.cancel_task(ws_message.conversation_id)
                        
                        await connection_manager.send_personal_message(
                            {
                                "type": "stop_acknowledged" if success else "stop_failed",
                                "conversationId": ws_message.conversation_id,
                                "success": success,
                                "timestamp": datetime.now().isoformat()
                            },
                            connection_id
                        )
                    else:
                        await connection_manager.send_personal_message(
                            {
                                "type": "error",
                                "error": "Missing conversation_id for stop request",
                                "timestamp": datetime.now().isoformat()
                            },
                            connection_id
                        )
                
                else:
                    logger.warning(
                        "unknown_websocket_message_type",
                        connection_id=connection_id,
                        message_type=ws_message.type
                    )
                    await connection_manager.send_personal_message(
                        {
                            "type": "error",
                            "error": f"Unknown message type: {ws_message.type}",
                            "timestamp": datetime.now().isoformat()
                        },
                        connection_id
                    )
            
            except Exception as e:
                logger.error(
                    "websocket_message_processing_error",
                    connection_id=connection_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True
                )
                await connection_manager.send_personal_message(
                    {
                        "type": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    },
                    connection_id
                )
    
    except WebSocketDisconnect:
        logger.info("websocket_disconnected", connection_id=connection_id, session_id=session_id)
    
    except Exception as e:
        logger.error(
            "websocket_connection_error",
            connection_id=connection_id,
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
    
    finally:
        # Always perform cleanup, regardless of how we exited the loop
        session_id_to_close = connection_manager.disconnect(connection_id)
        
        # Clean up all orchestrators for this connection
        orchestrator_count = len(active_conversation_orchestrators)
        active_conversation_orchestrators.clear()
        logger.info(
            "orchestrators_cleaned_up",
            connection_id=connection_id,
            orchestrator_count=orchestrator_count
        )
        
        # Close token tracking session and log final statistics
        if session_id_to_close:
            await token_manager.close_session(session_id_to_close)
            session_stats = await token_manager.get_session_summary(session_id_to_close)
            if session_stats:
                logger.info(
                    "session_token_usage_summary",
                    session_id=session_id_to_close,
                    total_cost=session_stats.get("total_cost", 0),
                    total_tokens=session_stats.get("total_tokens", 0),
                    total_requests=session_stats.get("total_requests", 0),
                    duration_seconds=session_stats.get("duration_seconds", 0),
                    usage_by_model=session_stats.get("usage_by_model", {}),
                    usage_by_agent=session_stats.get("usage_by_agent", {})
                )

