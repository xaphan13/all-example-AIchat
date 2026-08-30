"""Pytest configuration and shared fixtures."""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock, patch
import os

# Set test environment variables
os.environ["OPENROUTER_API_KEY"] = "test-key-openrouter"

from src.core.models import AgentType, AgentConfig, TaskRequest, StreamChunk
from src.agents.base_agent import BaseAgent
from src.agents.agent_factory import AgentFactory
from src.core.orchestrator.task_orchestrator import TaskOrchestrator


@pytest.fixture
def sample_agent_config() -> AgentConfig:
    """Create a sample agent configuration."""
    return AgentConfig(
        agent_id="test_agent",
        agent_type=AgentType.CLAUDE_MAIN,
        model="anthropic/claude-sonnet-4-5",
        temperature=0.7,
        max_tokens=1000,
        system_prompt="You are a test agent."
    )


@pytest.fixture
def mock_agent(sample_agent_config: AgentConfig) -> BaseAgent:
    """Create a mock agent for testing."""
    return BaseAgent(sample_agent_config)


@pytest.fixture
def sample_task_request() -> TaskRequest:
    """Create a sample task request."""
    return TaskRequest(
        message="What is the capital of France?",
        conversation_id=None,
        max_sub_agents=3,
        enable_collaboration=True
    )


@pytest.fixture
def mock_langchain_response():
    """Mock LangChain AIMessage response."""
    from langchain_core.messages import AIMessage
    return AIMessage(content="This is a test response.")


@pytest.fixture
def mock_streaming_response():
    """Mock streaming response from LangChain."""
    from langchain_core.messages import AIMessage
    
    async def mock_stream():
        chunks = [
            "Hello ",
            "world",
            "!",
        ]
        for content in chunks:
            yield AIMessage(content=content)
    
    return mock_stream()


@pytest.fixture
def orchestrator() -> TaskOrchestrator:
    """Create a task orchestrator instance."""
    return TaskOrchestrator()


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment between tests."""
    yield
    # Cleanup after each test
    pass

