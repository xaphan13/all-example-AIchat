"""Tests for BaseAgent class."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.core.models import AgentConfig, AgentType, AgentStatus, StreamChunk
from src.agents.base_agent import BaseAgent
from langchain_core.messages import AIMessage


class TestBaseAgent:
    """Test BaseAgent functionality."""
    
    def test_agent_initialization(self, sample_agent_config):
        """Test agent initialization."""
        agent = BaseAgent(sample_agent_config)
        assert agent.config == sample_agent_config
        assert agent.status == AgentStatus.IDLE
        assert len(agent.conversation_history) == 0
    
    def test_add_user_message(self, mock_agent):
        """Test adding user message to history."""
        mock_agent.add_user_message("Hello")
        assert len(mock_agent.conversation_history) == 1
        assert mock_agent.conversation_history[0]["role"] == "user"
        assert mock_agent.conversation_history[0]["content"] == "Hello"
    
    def test_get_history(self, mock_agent):
        """Test getting conversation history."""
        mock_agent.add_user_message("Hello")
        history = mock_agent.get_history()
        assert len(history) == 1
        # Should return a copy
        history.append({"role": "user", "content": "Test"})
        assert len(mock_agent.conversation_history) == 1
    
    def test_reset(self, mock_agent):
        """Test resetting agent state."""
        mock_agent.add_user_message("Hello")
        mock_agent.status = AgentStatus.COMPLETE
        
        mock_agent.reset()
        
        assert len(mock_agent.conversation_history) == 0
        assert mock_agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_stream_response(self, mock_agent):
        """Test streaming response."""
        # Create mock streaming response with LangChain AIMessage chunks
        async def mock_stream(messages):
            chunks = ["Hello ", "world", "!"]
            for content in chunks:
                yield AIMessage(content=content)
        
        # Mock the entire _chat_model with a Mock object
        mock_model = Mock()
        mock_model.astream = mock_stream
        mock_agent._chat_model = mock_model
        
        messages = [{"role": "user", "content": "Test"}]
        chunks = []
        
        async for chunk in mock_agent.stream_response(messages):
            chunks.append(chunk)
        
        # Should have content chunks + final chunk
        assert len(chunks) == 4
        assert chunks[0].content == "Hello "
        assert chunks[1].content == "world"
        assert chunks[2].content == "!"
        assert chunks[3].is_final is True
        assert mock_agent.status == AgentStatus.COMPLETE
    
    @pytest.mark.asyncio
    async def test_stream_response_error(self, mock_agent):
        """Test error handling in streaming."""
        # Mock the chat model's astream method to raise an error
        async def mock_stream_error(messages):
            raise Exception("API Error")
            yield  # Never reached, but makes this a generator
        
        mock_model = Mock()
        mock_model.astream = mock_stream_error
        mock_agent._chat_model = mock_model
        
        messages = [{"role": "user", "content": "Test"}]
        chunks = []
        
        async for chunk in mock_agent.stream_response(messages):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert "Error" in chunks[0].content
        assert chunks[0].is_final is True
        assert mock_agent.status == AgentStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_get_complete_response(self, mock_agent):
        """Test non-streaming response."""
        # Mock the chat model's ainvoke method to return an AIMessage
        async def mock_invoke(messages):
            return AIMessage(content="Complete response")
        
        mock_model = Mock()
        mock_model.ainvoke = mock_invoke
        mock_agent._chat_model = mock_model
        
        messages = [{"role": "user", "content": "Test"}]
        response = await mock_agent.get_complete_response(messages)
        
        assert response == "Complete response"
        assert mock_agent.status == AgentStatus.COMPLETE
        assert len(mock_agent.conversation_history) == 1
    
    @pytest.mark.asyncio
    async def test_get_complete_response_error(self, mock_agent):
        """Test error handling in complete response."""
        # Mock the chat model's ainvoke method to raise an error
        async def mock_invoke_error(messages):
            raise Exception("API Error")
        
        mock_model = Mock()
        mock_model.ainvoke = mock_invoke_error
        mock_agent._chat_model = mock_model
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(Exception) as exc_info:
            await mock_agent.get_complete_response(messages)
        
        assert "API Error" in str(exc_info.value)
        assert mock_agent.status == AgentStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_message_conversion(self, mock_agent):
        """Test that OpenAI-style messages are correctly converted to LangChain messages."""
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Store the messages that were passed to ainvoke
        called_with_messages = []
        
        async def mock_invoke(messages):
            called_with_messages.append(messages)
            return AIMessage(content="Response")
        
        mock_model = Mock()
        mock_model.ainvoke = mock_invoke
        mock_agent._chat_model = mock_model
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        await mock_agent.get_complete_response(messages)
        
        # Verify ainvoke was called with converted LangChain messages
        langchain_messages = called_with_messages[0]
        
        # Check that messages were converted correctly
        assert len(langchain_messages) == 4
        assert isinstance(langchain_messages[0], SystemMessage)
        assert isinstance(langchain_messages[1], HumanMessage)
        assert isinstance(langchain_messages[2], AIMessage)
        assert isinstance(langchain_messages[3], HumanMessage)

