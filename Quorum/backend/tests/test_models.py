"""Tests for data models."""
import pytest
from datetime import datetime
from pydantic import ValidationError

from src.core.models import (
    AgentType, AgentStatus, Message, AgentConfig, SubAgentQuery,
    AgentResponse, StreamChunk, TaskRequest, TaskResponse,
    AgentState, ConversationState
)


class TestEnums:
    """Test enum definitions."""
    
    def test_agent_type_values(self):
        """Test AgentType enum values."""
        assert AgentType.CLAUDE_MAIN.value == "claude-sonnet-4.5"
        assert AgentType.CLAUDE_SUB.value == "claude-sonnet-3.5"
        assert AgentType.GPT5.value == "gpt-5"
    
    def test_agent_status_values(self):
        """Test AgentStatus enum values."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.THINKING.value == "thinking"
        assert AgentStatus.RESPONDING.value == "responding"
        assert AgentStatus.COMPLETE.value == "complete"
        assert AgentStatus.ERROR.value == "error"


class TestMessage:
    """Test Message model."""
    
    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(
            id="msg_123",
            role="user",
            content="Hello, world!"
        )
        assert msg.id == "msg_123"
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert isinstance(msg.timestamp, datetime)
        assert msg.agent_id is None
    
    def test_message_with_agent_id(self):
        """Test message with agent_id."""
        msg = Message(
            id="msg_123",
            role="assistant",
            content="Response",
            agent_id="agent_456"
        )
        assert msg.agent_id == "agent_456"
    
    def test_invalid_role(self):
        """Test that invalid role raises validation error."""
        with pytest.raises(ValidationError):
            Message(
                id="msg_123",
                role="invalid_role",
                content="Test"
            )


class TestAgentConfig:
    """Test AgentConfig model."""
    
    def test_agent_config_creation(self):
        """Test creating agent configuration."""
        config = AgentConfig(
            agent_id="test_agent",
            agent_type=AgentType.CLAUDE_MAIN,
            model="anthropic/claude-sonnet-4-20250514",
            temperature=0.8,
            max_tokens=2000
        )
        assert config.agent_id == "test_agent"
        assert config.agent_type == AgentType.CLAUDE_MAIN
        assert config.temperature == 0.8
        assert config.max_tokens == 2000
    
    def test_agent_config_defaults(self):
        """Test default values in agent config."""
        config = AgentConfig(
            agent_id="test",
            agent_type=AgentType.CLAUDE_MAIN,
            model="test-model"
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.system_prompt is None


class TestSubAgentQuery:
    """Test SubAgentQuery model."""
    
    def test_sub_agent_query_creation(self):
        """Test creating a sub-agent query."""
        query = SubAgentQuery(
            agent_type=AgentType.CLAUDE_SUB,
            query="Analyze this data",
            context="Some context",
            priority=2
        )
        assert query.agent_type == AgentType.CLAUDE_SUB
        assert query.query == "Analyze this data"
        assert query.context == "Some context"
        assert query.priority == 2
    
    def test_sub_agent_query_defaults(self):
        """Test default values."""
        query = SubAgentQuery(
            agent_type=AgentType.GPT5,
            query="Test query"
        )
        assert query.context is None
        assert query.priority == 1


class TestStreamChunk:
    """Test StreamChunk model."""
    
    def test_stream_chunk_creation(self):
        """Test creating a stream chunk."""
        chunk = StreamChunk(
            agent_id="agent_123",
            content="Hello",
            is_final=False
        )
        assert chunk.agent_id == "agent_123"
        assert chunk.content == "Hello"
        assert chunk.is_final is False
        assert chunk.metadata is None
    
    def test_stream_chunk_with_metadata(self):
        """Test chunk with metadata."""
        chunk = StreamChunk(
            agent_id="agent_123",
            content="Done",
            is_final=True,
            metadata={"tokens": 100}
        )
        assert chunk.is_final is True
        assert chunk.metadata["tokens"] == 100


class TestTaskRequest:
    """Test TaskRequest model."""
    
    def test_task_request_creation(self):
        """Test creating a task request."""
        task = TaskRequest(
            message="What is AI?",
            conversation_id="conv_123",
            max_sub_agents=2,
            enable_collaboration=False
        )
        assert task.message == "What is AI?"
        assert task.conversation_id == "conv_123"
        assert task.max_sub_agents == 2
        assert task.enable_collaboration is False
    
    def test_task_request_defaults(self):
        """Test default values."""
        task = TaskRequest(message="Test")
        assert task.conversation_id is None
        assert task.max_sub_agents == 3
        assert task.enable_collaboration is True


class TestAgentState:
    """Test AgentState model."""
    
    def test_agent_state_creation(self):
        """Test creating agent state."""
        state = AgentState(
            agent_id="agent_123",
            agent_type=AgentType.CLAUDE_MAIN,
            status=AgentStatus.THINKING,
            current_message="Processing...",
            progress=0.5
        )
        assert state.agent_id == "agent_123"
        assert state.status == AgentStatus.THINKING
        assert state.progress == 0.5
        assert state.current_message == "Processing..."


class TestConversationState:
    """Test ConversationState model."""
    
    def test_conversation_state_creation(self):
        """Test creating conversation state."""
        state = ConversationState(
            conversation_id="conv_123",
            is_complete=False
        )
        assert state.conversation_id == "conv_123"
        assert state.is_complete is False
        assert len(state.messages) == 0
        assert len(state.active_agents) == 0
        assert isinstance(state.created_at, datetime)

