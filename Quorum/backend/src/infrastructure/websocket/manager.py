"""
WebSocket connection manager for real-time bidirectional streaming.
Manages multiple client connections and message routing.
"""
import asyncio
import json
from typing import Dict, Set, Optional, Any
from datetime import datetime
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        # Active connections: {connection_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Conversation subscriptions: {conversation_id: set(connection_ids)}
        self.conversation_subscribers: Dict[str, Set[str]] = {}
        
        # Connection metadata: {connection_id: metadata}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Active tasks: {conversation_id: orchestrator}
        self.active_tasks: Dict[str, Any] = {}
        
        # Session tracking: {connection_id: session_id}
        self.connection_sessions: Dict[str, str] = {}
        
        logger.info("connection_manager_initialized")
    
    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            
        Returns:
            connection_id: Unique identifier for this connection
        """
        await websocket.accept()
        
        connection_id = f"conn_{uuid.uuid4().hex[:12]}"
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        self.active_connections[connection_id] = websocket
        self.connection_sessions[connection_id] = session_id
        self.connection_metadata[connection_id] = {
            "connected_at": datetime.now().isoformat(),
            "subscriptions": set(),
            "session_id": session_id
        }
        
        logger.info(
            "websocket_connected",
            connection_id=connection_id,
            session_id=session_id,
            total_connections=len(self.active_connections)
        )
        
        return connection_id
    
    def disconnect(self, connection_id: str) -> Optional[str]:
        """
        Remove a WebSocket connection.
        
        Args:
            connection_id: The connection identifier
            
        Returns:
            session_id: The session ID associated with this connection, if any
        """
        session_id = self.connection_sessions.get(connection_id)
        
        # Remove from active connections
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        # Remove session mapping
        if connection_id in self.connection_sessions:
            del self.connection_sessions[connection_id]
        
        # Remove from all conversation subscriptions
        for subscribers in self.conversation_subscribers.values():
            subscribers.discard(connection_id)
        
        # Clean up empty subscriptions
        empty_convs = [
            conv_id for conv_id, subs in self.conversation_subscribers.items()
            if not subs
        ]
        for conv_id in empty_convs:
            del self.conversation_subscribers[conv_id]
        
        # Remove metadata
        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]
        
        logger.info(
            "websocket_disconnected",
            connection_id=connection_id,
            session_id=session_id,
            total_connections=len(self.active_connections)
        )
        
        return session_id
    
    def subscribe_to_conversation(self, connection_id: str, conversation_id: str):
        """
        Subscribe a connection to a conversation's events.
        
        Args:
            connection_id: The connection identifier
            conversation_id: The conversation to subscribe to
        """
        if conversation_id not in self.conversation_subscribers:
            self.conversation_subscribers[conversation_id] = set()
        
        self.conversation_subscribers[conversation_id].add(connection_id)
        
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["subscriptions"].add(conversation_id)
        
        logger.debug(
            "conversation_subscribed",
            connection_id=connection_id,
            conversation_id=conversation_id,
            subscriber_count=len(self.conversation_subscribers[conversation_id])
        )
    
    def unsubscribe_from_conversation(self, connection_id: str, conversation_id: str):
        """
        Unsubscribe a connection from a conversation.
        
        Args:
            connection_id: The connection identifier
            conversation_id: The conversation to unsubscribe from
        """
        if conversation_id in self.conversation_subscribers:
            self.conversation_subscribers[conversation_id].discard(connection_id)
            
            if not self.conversation_subscribers[conversation_id]:
                del self.conversation_subscribers[conversation_id]
        
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["subscriptions"].discard(conversation_id)
        
        logger.debug(
            "conversation_unsubscribed",
            connection_id=connection_id,
            conversation_id=conversation_id
        )
    
    async def send_personal_message(self, message: Dict[str, Any], connection_id: str):
        """
        Send a message to a specific connection.
        
        Args:
            message: The message to send (will be JSON serialized)
            connection_id: Target connection identifier
        """
        websocket = self.active_connections.get(connection_id)
        if websocket:
            try:
                await websocket.send_json(message)
                logger.debug(
                    "message_sent_personal",
                    connection_id=connection_id,
                    message_type=message.get("type")
                )
            except Exception as e:
                logger.error(
                    "send_personal_message_error",
                    connection_id=connection_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                # Connection might be dead, disconnect it
                self.disconnect(connection_id)
    
    async def broadcast_to_conversation(
        self,
        message: Dict[str, Any],
        conversation_id: str
    ):
        """
        Broadcast a message to all subscribers of a conversation.
        
        Args:
            message: The message to broadcast (will be JSON serialized)
            conversation_id: The conversation identifier
        """
        subscribers = self.conversation_subscribers.get(conversation_id, set())
        
        if not subscribers:
            logger.debug(
                "no_subscribers_for_broadcast",
                conversation_id=conversation_id
            )
            return
        
        logger.debug(
            "broadcasting_to_conversation",
            conversation_id=conversation_id,
            subscriber_count=len(subscribers),
            message_type=message.get("type")
        )
        
        # Send to all subscribers concurrently
        tasks = []
        for connection_id in list(subscribers):  # Copy to avoid modification during iteration
            websocket = self.active_connections.get(connection_id)
            if websocket:
                tasks.append(self._send_with_error_handling(
                    websocket,
                    message,
                    connection_id
                ))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_with_error_handling(
        self,
        websocket: WebSocket,
        message: Dict[str, Any],
        connection_id: str
    ):
        """Send message with error handling."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(
                "broadcast_send_error",
                connection_id=connection_id,
                error=str(e),
                error_type=type(e).__name__
            )
            # Mark for disconnection
            self.disconnect(connection_id)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
        """
        logger.debug(
            "broadcasting_to_all",
            connection_count=len(self.active_connections),
            message_type=message.get("type")
        )
        
        tasks = [
            self._send_with_error_handling(ws, message, conn_id)
            for conn_id, ws in list(self.active_connections.items())
        ]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
    
    def get_conversation_subscriber_count(self, conversation_id: str) -> int:
        """Get the number of subscribers for a conversation."""
        return len(self.conversation_subscribers.get(conversation_id, set()))
    
    def register_task(self, conversation_id: str, orchestrator: Any):
        """
        Register an active task for a conversation.
        
        Args:
            conversation_id: The conversation identifier
            orchestrator: The TaskOrchestrator instance
        """
        self.active_tasks[conversation_id] = orchestrator
        logger.debug(
            "task_registered",
            conversation_id=conversation_id,
            active_task_count=len(self.active_tasks)
        )
    
    def unregister_task(self, conversation_id: str):
        """
        Unregister an active task.
        
        Args:
            conversation_id: The conversation identifier
        """
        if conversation_id in self.active_tasks:
            del self.active_tasks[conversation_id]
            logger.debug(
                "task_unregistered",
                conversation_id=conversation_id,
                active_task_count=len(self.active_tasks)
            )
    
    def cancel_task(self, conversation_id: str) -> bool:
        """
        Cancel an active task.
        
        Args:
            conversation_id: The conversation identifier
            
        Returns:
            True if task was found and cancelled, False otherwise
        """
        orchestrator = self.active_tasks.get(conversation_id)
        if orchestrator:
            logger.info("cancelling_task", conversation_id=conversation_id)
            orchestrator.cancel()
            return True
        else:
            logger.warning("task_not_found_for_cancellation", conversation_id=conversation_id)
            return False
    
    def get_session_id(self, connection_id: str) -> Optional[str]:
        """
        Get the session ID for a connection.
        
        Args:
            connection_id: The connection identifier
            
        Returns:
            The session ID, or None if not found
        """
        return self.connection_sessions.get(connection_id)


# Global connection manager instance
connection_manager = ConnectionManager()

