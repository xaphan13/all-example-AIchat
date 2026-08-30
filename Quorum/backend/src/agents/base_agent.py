"""
Base agent class providing common functionality for all AI agents.
Handles LangChain integration, streaming, and error handling.
"""
import asyncio
import os
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.core.models import AgentConfig, AgentType, AgentStatus, StreamChunk
from src.infrastructure.logging.config import get_logger
from src.core.config import settings
from src.core.settings_service import get_settings_service
from src.infrastructure.tracking.callback_handler import TokenTrackingCallback
from src.infrastructure.tracking.token_manager import get_token_manager
from src.tools.registry import ToolRegistry

logger = get_logger(__name__)


class BaseAgent:
    """Base class for all AI agents in the system."""
    
    def __init__(self, config: AgentConfig, session_id: Optional[str] = None, tool_registry: Optional[ToolRegistry] = None):
        """
        Initialize the agent with configuration.
        
        Args:
            config: Agent configuration
            session_id: Optional session ID for token tracking
            tool_registry: Optional tool registry for agent tools
        """
        self.config = config
        self.status = AgentStatus.IDLE
        self.conversation_history = []
        self.session_id = session_id
        self._token_manager = get_token_manager()
        self._settings_service = get_settings_service()
        self._tool_registry = tool_registry
        
        # Initialize token tracking callbacks (separate for streaming and non-streaming)
        self._token_callback_non_streaming = TokenTrackingCallback(
            agent_id=config.agent_id,
            session_id=session_id,
            on_usage_callback=self._on_token_usage,
            is_streaming=False
        )
        self._token_callback_streaming = TokenTrackingCallback(
            agent_id=config.agent_id,
            session_id=session_id,
            on_usage_callback=self._on_token_usage,
            is_streaming=True
        )
        
        # Store API key - will be initialized during first use
        self._api_key = None
        
        self._chat_model = None
        self._chat_model_streaming = None
        self._model_initialized = False
        self._streaming_model_initialized = False
    
    async def _initialize_chat_model(self, use_streaming_callback: bool = False):
        """
        Initialize the appropriate LangChain chat model based on config.
        
        Args:
            use_streaming_callback: If True, use streaming callback (suppresses token usage warnings)
        """
        # Return cached model if already initialized
        if use_streaming_callback:
            if self._streaming_model_initialized and self._chat_model_streaming is not None:
                return self._chat_model_streaming
        else:
            if self._model_initialized and self._chat_model is not None:
                return self._chat_model
            
        model_name = self.config.model
        
        # Get API key from settings service (database first, then environment)
        openrouter_key = await self._settings_service.get_openrouter_api_key()
        self._api_key = openrouter_key
        
        # Choose appropriate callback based on whether we're streaming
        callback = self._token_callback_streaming if use_streaming_callback else self._token_callback_non_streaming
        callbacks = [callback]
        
        # Get tool bindings if tool registry is available
        tool_kwargs = {}
        if self._tool_registry and self._tool_registry.list_tools():
            tool_schemas = self._tool_registry.get_all_schemas()
            # Convert to LangChain format
            tool_kwargs["tools"] = tool_schemas
        
        # Use OpenRouter API (OpenAI-compatible interface)
        # OpenRouter supports all providers through a unified endpoint
        chat_model = ChatOpenAI(
            model=model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            callbacks=callbacks,
            **tool_kwargs
        )
        
        # Cache the model appropriately
        if use_streaming_callback:
            self._chat_model_streaming = chat_model
            self._streaming_model_initialized = True
        else:
            self._chat_model = chat_model
            self._model_initialized = True
        
        logger.debug(
            "chat_model_initialized",
            agent_id=self.config.agent_id,
            model=model_name,
            provider=self._get_provider_name(),
            is_streaming=use_streaming_callback
        )
        return chat_model
    
    def _get_provider_name(self) -> str:
        """Get the provider name for this agent's model."""
        model_name = self.config.model.lower()
        # Extract provider from OpenRouter model format (provider/model)
        if "/" in model_name:
            return model_name.split("/")[0]
        return "openrouter"
        
    async def stream_response(
        self,
        messages: list[dict],
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a response from the agent.
        
        Args:
            messages: List of message dicts in OpenAI format
            **kwargs: Additional parameters for the LLM call
            
        Yields:
            StreamChunk objects containing response fragments
        """
        self.status = AgentStatus.THINKING
        
        logger.debug(
            "agent_stream_started",
            agent_id=self.config.agent_id,
            agent_type=self.config.agent_type.value,
            model=self.config.model,
            message_count=len(messages)
        )
        
        try:
            # Ensure chat model is initialized with latest API keys and streaming callback
            chat_model = await self._initialize_chat_model(use_streaming_callback=True)
            
            # Convert OpenAI-style messages to LangChain messages
            langchain_messages = self._convert_to_langchain_messages(messages)
            
            self.status = AgentStatus.RESPONDING
            accumulated_content = ""
            
            # Stream response using LangChain's async streaming
            async for chunk in chat_model.astream(langchain_messages):
                if chunk.content:
                    content = chunk.content
                    accumulated_content += content
                    
                    yield StreamChunk(
                        agent_id=self.config.agent_id,
                        content=content,
                        is_final=False
                    )
            
            # Send final chunk
            yield StreamChunk(
                agent_id=self.config.agent_id,
                content="",
                is_final=True,
                metadata={"total_length": len(accumulated_content)}
            )
            
            self.status = AgentStatus.COMPLETE
            
            logger.info(
                "agent_stream_completed",
                agent_id=self.config.agent_id,
                agent_type=self.config.agent_type.value,
                response_length=len(accumulated_content)
            )
            
            # Store in conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": accumulated_content
            })
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(
                "agent_stream_error",
                agent_id=self.config.agent_id,
                agent_type=self.config.agent_type.value,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            yield StreamChunk(
                agent_id=self.config.agent_id,
                content=f"Error: {str(e)}",
                is_final=True,
                metadata={"error": True}
            )
    
    async def get_complete_response(
        self,
        messages: list[dict],
        **kwargs
    ) -> str:
        """
        Get a complete (non-streaming) response from the agent.
        
        Args:
            messages: List of message dicts in OpenAI format
            **kwargs: Additional parameters for the LLM call
            
        Returns:
            Complete response string
        """
        self.status = AgentStatus.THINKING
        
        logger.debug(
            "agent_request_started",
            agent_id=self.config.agent_id,
            agent_type=self.config.agent_type.value,
            model=self.config.model,
            message_count=len(messages)
        )
        
        try:
            # Ensure chat model is initialized with latest API keys
            chat_model = await self._initialize_chat_model()
            
            # Convert OpenAI-style messages to LangChain messages
            langchain_messages = self._convert_to_langchain_messages(messages)
            
            # Get response using LangChain's async invoke
            response = await chat_model.ainvoke(langchain_messages)
            content = response.content
            
            self.status = AgentStatus.COMPLETE
            
            logger.info(
                "agent_request_completed",
                agent_id=self.config.agent_id,
                agent_type=self.config.agent_type.value,
                response_length=len(content)
            )
            
            self.conversation_history.append({
                "role": "assistant",
                "content": content
            })
            
            return content
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(
                "agent_request_error",
                agent_id=self.config.agent_id,
                agent_type=self.config.agent_type.value,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise Exception(f"Agent {self.config.agent_id} error: {str(e)}")
    
    def _convert_to_langchain_messages(self, messages: list[dict]) -> list:
        """
        Convert OpenAI-style messages to LangChain message objects.
        
        Args:
            messages: List of message dicts in OpenAI format
            
        Returns:
            List of LangChain message objects
        """
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:  # user or any other role defaults to human
                langchain_messages.append(HumanMessage(content=content))
        
        return langchain_messages
    
    def add_user_message(self, content: str):
        """Add a user message to conversation history."""
        self.conversation_history.append({
            "role": "user",
            "content": content
        })
    
    def get_history(self) -> list[dict]:
        """Get the conversation history."""
        return self.conversation_history.copy()
    
    async def _on_token_usage(self, usage):
        """
        Callback for when token usage is tracked.
        
        Args:
            usage: TokenUsage object
        """
        await self._token_manager.record_usage(usage, self.session_id)
    
    async def get_token_stats(self) -> Dict[str, Any]:
        """
        Get token usage statistics for this agent's session.
        
        Returns:
            Dictionary with token usage statistics
        """
        if self.session_id:
            return await self._token_manager.get_session_summary(self.session_id)
        return None
    
    async def refresh_api_keys(self):
        """
        Refresh API keys from settings service.
        Useful when keys are updated in the database.
        """
        self._model_initialized = False
        self._streaming_model_initialized = False
        self._chat_model = None
        self._chat_model_streaming = None
        logger.info(
            "api_keys_refresh_requested",
            agent_id=self.config.agent_id
        )
        # Keys will be reloaded on next model use
    
    def set_tool_registry(self, tool_registry: ToolRegistry):
        """
        Set or update the tool registry for this agent.
        This will force model reinitialization on next use.
        
        Args:
            tool_registry: ToolRegistry instance
        """
        self._tool_registry = tool_registry
        # Force model reinitialization to include new tools
        self._model_initialized = False
        self._streaming_model_initialized = False
        self._chat_model = None
        self._chat_model_streaming = None
        logger.info(
            "tool_registry_updated",
            agent_id=self.config.agent_id,
            tool_count=len(tool_registry.list_tools()) if tool_registry else 0
        )
    
    def get_tool_registry(self) -> Optional[ToolRegistry]:
        """Get the current tool registry."""
        return self._tool_registry
    
    async def execute_tool(self, tool_name: str, **kwargs):
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution result
        """
        if not self._tool_registry:
            logger.error(
                "tool_execution_no_registry",
                agent_id=self.config.agent_id,
                tool_name=tool_name
            )
            from src.tools.base import ToolResult
            return ToolResult(
                success=False,
                error="No tool registry configured for this agent"
            )
        
        return await self._tool_registry.execute_tool(tool_name, **kwargs)
    
    def reset(self):
        """Reset the agent state."""
        logger.debug(
            "agent_reset",
            agent_id=self.config.agent_id,
            history_length=len(self.conversation_history)
        )
        self.conversation_history = []
        self.status = AgentStatus.IDLE

