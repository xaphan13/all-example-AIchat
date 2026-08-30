"""Tests for TaskOrchestrator class."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
from src.core.models import TaskRequest, AgentType
from src.core.orchestrator.task_orchestrator import TaskOrchestrator


class TestTaskOrchestrator:
    """Test TaskOrchestrator functionality."""
    
    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initialization."""
        assert orchestrator.main_agent is None
        assert len(orchestrator.active_sub_agents) == 0
        assert orchestrator.conversation_id is None
    
    def test_reset(self, orchestrator):
        """Test resetting orchestrator."""
        orchestrator.conversation_id = "conv_123"
        orchestrator.main_agent = Mock()
        orchestrator.active_sub_agents["agent_1"] = Mock()
        
        orchestrator.reset()
        
        assert orchestrator.main_agent is None
        assert len(orchestrator.active_sub_agents) == 0
        assert orchestrator.conversation_id is None
    
    @pytest.mark.asyncio
    async def test_process_task_creates_conversation_id(self, orchestrator, sample_task_request):
        """Test that process_task creates a conversation ID."""
        with patch('agents.agent_factory.AgentFactory.create_main_agent') as mock_factory:
            mock_agent = Mock()
            mock_agent.config = Mock()
            mock_agent.config.agent_id = "main"
            mock_agent.config.system_prompt = "Test"
            
            async def mock_stream(*args, **kwargs):
                yield Mock(content="Test", is_final=True, agent_id="main")
            
            mock_agent.stream_response = mock_stream
            mock_agent.get_complete_response = AsyncMock(return_value='{"delegate": false, "reasoning": "Simple task"}')
            mock_factory.return_value = mock_agent
            
            events = []
            async for event in orchestrator.process_task(sample_task_request):
                events.append(event)
            
            assert orchestrator.conversation_id is not None
            assert orchestrator.conversation_id.startswith("conv_")
    
    @pytest.mark.asyncio
    async def test_process_task_uses_provided_conversation_id(self, orchestrator):
        """Test using provided conversation ID."""
        task = TaskRequest(
            message="Test",
            conversation_id="custom_conv_id",
            enable_collaboration=False
        )
        
        with patch('agents.agent_factory.AgentFactory.create_main_agent') as mock_factory:
            mock_agent = Mock()
            mock_agent.config = Mock()
            mock_agent.config.agent_id = "main"
            mock_agent.config.system_prompt = "Test"
            
            async def mock_stream(*args, **kwargs):
                yield Mock(content="Test", is_final=True, agent_id="main")
            
            mock_agent.stream_response = mock_stream
            mock_factory.return_value = mock_agent
            
            events = []
            async for event in orchestrator.process_task(task):
                events.append(event)
            
            assert orchestrator.conversation_id == "custom_conv_id"
    
    @pytest.mark.asyncio
    async def test_process_task_event_types(self, orchestrator, sample_task_request):
        """Test that process_task emits correct event types."""
        sample_task_request.enable_collaboration = False
        
        with patch('agents.agent_factory.AgentFactory.create_main_agent') as mock_factory:
            mock_agent = Mock()
            mock_agent.config = Mock()
            mock_agent.config.agent_id = "main"
            mock_agent.config.system_prompt = "Test"
            
            async def mock_stream(*args, **kwargs):
                yield Mock(content="Response ", is_final=False, agent_id="main")
                yield Mock(content="complete", is_final=True, agent_id="main")
            
            mock_agent.stream_response = mock_stream
            mock_factory.return_value = mock_agent
            
            events = []
            async for event in orchestrator.process_task(sample_task_request):
                events.append(event)
            
            event_types = [e["type"] for e in events]
            assert "init" in event_types
            assert "agent_status" in event_types
            assert "stream" in event_types
            assert "complete" in event_types
    
    def test_prepare_main_agent_messages(self, orchestrator):
        """Test preparing messages for main agent."""
        with patch('agents.agent_factory.AgentFactory.create_main_agent') as mock_factory:
            mock_agent = Mock()
            mock_agent.config = Mock()
            mock_agent.config.system_prompt = "Test prompt"
            mock_factory.return_value = mock_agent
            orchestrator.main_agent = mock_agent
            
            messages = orchestrator._prepare_main_agent_messages("User message")
            
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "Test prompt"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "User message"
    
    def test_prepare_synthesis_messages(self, orchestrator):
        """Test preparing synthesis messages."""
        with patch('agents.agent_factory.AgentFactory.create_main_agent') as mock_factory:
            mock_agent = Mock()
            mock_agent.config = Mock()
            mock_agent.config.system_prompt = "Test prompt"
            mock_factory.return_value = mock_agent
            orchestrator.main_agent = mock_agent
            
            sub_responses = [
                {
                    "agent_type": "claude-sub",
                    "content": "Sub response 1",
                    "agent_id": "sub_1"
                },
                {
                    "agent_type": "gpt-5",
                    "content": "Sub response 2",
                    "agent_id": "sub_2"
                }
            ]
            
            messages = orchestrator._prepare_synthesis_messages(
                "Original request",
                sub_responses
            )
            
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert "Original request" in messages[1]["content"]
            assert "claude-sub" in messages[1]["content"]
            assert "Sub response 1" in messages[1]["content"]
    
    @pytest.mark.asyncio
    async def test_get_delegation_plan_no_delegation(self, orchestrator):
        """Test delegation plan when no delegation needed."""
        with patch('agents.agent_factory.AgentFactory.create_main_agent') as mock_factory:
            mock_agent = Mock()
            mock_agent.config = Mock()
            mock_agent.config.system_prompt = "Test"
            mock_agent.get_complete_response = AsyncMock(
                return_value='{"delegate": false, "reasoning": "Simple task"}'
            )
            mock_factory.return_value = mock_agent
            orchestrator.main_agent = mock_agent
            
            plan = await orchestrator._get_delegation_plan("Simple question", 3)
            
            assert plan["delegate"] is False
            assert "reasoning" in plan
    
    @pytest.mark.asyncio
    async def test_get_delegation_plan_with_delegation(self, orchestrator):
        """Test delegation plan with sub-agents."""
        with patch('agents.agent_factory.AgentFactory.create_main_agent') as mock_factory:
            mock_agent = Mock()
            mock_agent.config = Mock()
            mock_agent.config.system_prompt = "Test"
            
            response_json = {
                "delegate": True,
                "reasoning": "Need expert help",
                "sub_queries": [
                    {
                        "agent_type": "claude-sub",
                        "query": "Analyze data",
                        "priority": 1
                    }
                ]
            }
            mock_agent.get_complete_response = AsyncMock(
                return_value=json.dumps(response_json)
            )
            mock_factory.return_value = mock_agent
            orchestrator.main_agent = mock_agent
            
            plan = await orchestrator._get_delegation_plan("Complex question", 3)
            
            assert plan["delegate"] is True
            assert len(plan["sub_queries"]) == 1
            assert plan["sub_queries"][0]["agent_type"] == "claude-sub"
    
    @pytest.mark.asyncio
    async def test_get_delegation_plan_with_markdown(self, orchestrator):
        """Test parsing delegation plan from markdown JSON."""
        with patch('agents.agent_factory.AgentFactory.create_main_agent') as mock_factory:
            mock_agent = Mock()
            mock_agent.config = Mock()
            mock_agent.config.system_prompt = "Test"
            
            markdown_response = '''```json
{
    "delegate": false,
    "reasoning": "In markdown"
}
```'''
            mock_agent.get_complete_response = AsyncMock(return_value=markdown_response)
            mock_factory.return_value = mock_agent
            orchestrator.main_agent = mock_agent
            
            plan = await orchestrator._get_delegation_plan("Question", 3)
            
            assert plan["delegate"] is False
    
    @pytest.mark.asyncio
    async def test_execute_single_sub_agent(self, orchestrator):
        """Test executing a single sub-agent."""
        mock_agent = Mock()
        mock_agent.config = Mock()
        mock_agent.config.agent_id = "sub_1"
        mock_agent.config.agent_type = AgentType.CLAUDE_SUB
        mock_agent.config.system_prompt = "Sub agent"
        mock_agent.get_complete_response = AsyncMock(return_value="Sub agent response")
        
        result = await orchestrator._execute_single_sub_agent(mock_agent, "Test query")
        
        assert result["agent_id"] == "sub_1"
        assert result["agent_type"] == AgentType.CLAUDE_SUB.value
        assert result["content"] == "Sub agent response"

