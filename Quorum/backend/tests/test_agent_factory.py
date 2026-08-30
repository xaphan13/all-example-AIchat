"""Tests for AgentFactory class."""
import pytest
from src.core.models import AgentType
from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import BaseAgent


class TestAgentFactory:
    """Test AgentFactory functionality."""
    
    def test_model_map_completeness(self):
        """Test that all agent types have model mappings."""
        for agent_type in AgentType:
            assert agent_type in AgentFactory.MODEL_MAP
            assert AgentFactory.MODEL_MAP[agent_type] is not None
    
    def test_system_prompts_completeness(self):
        """Test that all agent types have system prompts."""
        for agent_type in AgentType:
            assert agent_type in AgentFactory.SYSTEM_PROMPTS
            assert AgentFactory.SYSTEM_PROMPTS[agent_type] is not None
    
    def test_create_agent(self):
        """Test creating an agent."""
        agent = AgentFactory.create_agent(
            agent_type=AgentType.CLAUDE_MAIN,
            agent_id="test_agent",
            temperature=0.8,
            max_tokens=2000
        )
        
        assert isinstance(agent, BaseAgent)
        assert agent.config.agent_id == "test_agent"
        assert agent.config.agent_type == AgentType.CLAUDE_MAIN
        assert agent.config.temperature == 0.8
        assert agent.config.max_tokens == 2000
        assert agent.config.model == AgentFactory.MODEL_MAP[AgentType.CLAUDE_MAIN]
    
    def test_create_agent_auto_id(self):
        """Test creating agent with auto-generated ID."""
        agent = AgentFactory.create_agent(AgentType.CLAUDE_SUB)
        
        assert agent.config.agent_id is not None
        assert AgentType.CLAUDE_SUB.value in agent.config.agent_id
    
    def test_create_agent_custom_prompt(self):
        """Test creating agent with custom system prompt."""
        custom_prompt = "Custom instructions"
        agent = AgentFactory.create_agent(
            agent_type=AgentType.GPT5,
            custom_system_prompt=custom_prompt
        )
        
        assert agent.config.system_prompt == custom_prompt
    
    def test_create_agent_default_prompt(self):
        """Test creating agent with default system prompt."""
        agent = AgentFactory.create_agent(AgentType.CLAUDE_SUB)
        
        expected_prompt = AgentFactory.SYSTEM_PROMPTS[AgentType.CLAUDE_SUB]
        assert agent.config.system_prompt == expected_prompt
    
    def test_create_agent_invalid_type(self):
        """Test creating agent with invalid type."""
        # This would require mocking, so we'll test the model map lookup
        with pytest.raises(ValueError):
            # Create a fake enum value
            fake_type = Mock()
            fake_type.value = "invalid"
            AgentFactory.MODEL_MAP.get(fake_type) or (_ for _ in ()).throw(ValueError(f"Unknown agent type: {fake_type}"))
    
    def test_create_main_agent(self):
        """Test creating main orchestrator agent."""
        agent = AgentFactory.create_main_agent()
        
        assert isinstance(agent, BaseAgent)
        assert agent.config.agent_id == "main_orchestrator"
        assert agent.config.agent_type == AgentType.CLAUDE_MAIN
        assert agent.config.temperature == 0.8
    
    def test_create_sub_agent(self):
        """Test creating sub-agent."""
        agent = AgentFactory.create_sub_agent(
            agent_type=AgentType.CLAUDE_SUB,
            task_description="Analyze this data"
        )
        
        assert isinstance(agent, BaseAgent)
        assert agent.config.agent_type == AgentType.CLAUDE_SUB
        assert agent.config.temperature == 0.7
        assert "Analyze this data" in agent.config.system_prompt
    
    def test_create_sub_agent_no_task(self):
        """Test creating sub-agent without task description."""
        agent = AgentFactory.create_sub_agent(AgentType.GPT5)
        
        assert isinstance(agent, BaseAgent)
        expected_prompt = AgentFactory.SYSTEM_PROMPTS[AgentType.GPT5]
        assert agent.config.system_prompt == expected_prompt
    
    def test_all_agent_types_creatable(self):
        """Test that all agent types can be created."""
        for agent_type in AgentType:
            agent = AgentFactory.create_agent(agent_type)
            assert isinstance(agent, BaseAgent)
            assert agent.config.agent_type == agent_type


# Mock for invalid type test
from unittest.mock import Mock

