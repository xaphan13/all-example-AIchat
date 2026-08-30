"""
Factory for creating different types of agents with appropriate configurations.
Maps agent types to their corresponding LiteLLM model strings.
"""
from typing import Optional
import uuid

from src.core.models import AgentType, AgentConfig
from src.agents.base_agent import BaseAgent
from src.infrastructure.logging.config import get_logger
from src.tools.registry import ToolRegistry

logger = get_logger(__name__)


class AgentFactory:
    """Factory for creating configured agents."""
    
    # Map agent types to OpenRouter model identifiers
    # Format: provider/model-name
    # Updated model names for Quorum delegation (Nov 2024)
    MODEL_MAP = {
        AgentType.CLAUDE_MAIN: "anthropic/claude-3.5-sonnet",  # Claude 3.5 Sonnet (main orchestrator)
        AgentType.CLAUDE_SUB: "anthropic/claude-3-5-haiku",    # Claude 3.5 Haiku (fast, efficient)
        AgentType.GPT5: "openai/gpt-4o",                       # GPT-4o (balanced reasoning)
    }
    
    # Quorum models for multi-agent collaboration (in delegation order)
    QUORUM_MODELS = [
        "anthropic/claude-3-5-haiku",      # Claude Haiku 3.5 - Fast analysis
        "google/gemini-2.0-flash-exp",     # Gemini 2.0 Flash - Multimodal thinking
        "x-ai/grok-beta",                  # Grok Beta - Real-time insights
        "openai/gpt-4o",                   # GPT-4o - Creative reasoning
    ]
    
    # System prompts for different agent types
    SYSTEM_PROMPTS = {
        AgentType.CLAUDE_MAIN: """You are the main orchestrator agent. Your role is to:
1. Understand complex user requests
2. Decide which sub-agents to consult for help
3. Synthesize their responses into a coherent answer
4. Coordinate the overall task completion

## Available Tools
You have access to external tools that enhance your capabilities:

### web_search Tool
Use the web_search tool when you need current, real-time information:
- Current events, news, or recent developments
- Latest statistics, data, or research
- Information that may have changed since your training
- Specific facts about companies, products, or websites
- Verification of time-sensitive information

**How to use web_search:**
- Tool name: "web_search"
- Parameters:
  - query (required): Clear, specific search query with relevant keywords
  - num_results (optional, 1-10): Number of results to retrieve (default: 5)
  - search_type (optional): "general", "news", or "images" (default: "general")

**Best practices:**
- Use specific, well-crafted queries (e.g., "latest AI developments 2024" not just "AI")
- Request appropriate number of results (3-5 for most queries)
- Use "news" type for recent events
- The user will see your web searches in a special display panel
- Always explain why you're searching and what you found

## Delegation
When you need help, you can request assistance from:
- Claude sub-agents (for detailed analysis)
- GPT agents (for creative tasks)

Be strategic about when to involve other agents and when to use tools.""",
        
        AgentType.CLAUDE_SUB: """You are a specialized Claude assistant. Provide detailed,
accurate analysis for the specific query you receive. Focus on depth and precision.

## Available Tools
You have access to the web_search tool for gathering current information:
- Use it when you need real-time data or recent developments
- Format: web_search(query="your search", num_results=5, search_type="general")
- Your tool usage will be visible to users in a dedicated display
- Always explain your search rationale and findings""",
        
        AgentType.GPT5: """You are a GPT assistant specializing in creative and analytical tasks.
Provide clear, well-structured responses with practical insights.

## Available Tools
You can use the web_search tool to access current information:
- Essential for time-sensitive queries or recent developments
- Syntax: web_search(query="specific search terms", num_results=5)
- Users can see your research process in the tool usage panel
- Integrate search results naturally into your responses""",
    }
    
    @classmethod
    def create_agent(
        cls,
        agent_type: AgentType,
        agent_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        custom_system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        tool_registry: Optional[ToolRegistry] = None
    ) -> BaseAgent:
        """
        Create an agent of the specified type.
        
        Args:
            agent_type: Type of agent to create
            agent_id: Optional custom agent ID
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            custom_system_prompt: Optional custom system prompt
            session_id: Optional session ID for token tracking
            tool_registry: Optional tool registry for agent tools
            
        Returns:
            Configured BaseAgent instance
        """
        if agent_id is None:
            agent_id = f"{agent_type.value}_{uuid.uuid4().hex[:8]}"
        
        model = cls.MODEL_MAP.get(agent_type)
        if not model:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        system_prompt = custom_system_prompt or cls.SYSTEM_PROMPTS.get(agent_type)
        
        config = AgentConfig(
            agent_id=agent_id,
            agent_type=agent_type,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt
        )
        
        logger.debug(
            "agent_created",
            agent_id=agent_id,
            agent_type=agent_type.value,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            session_id=session_id,
            has_tools=bool(tool_registry)
        )
        
        return BaseAgent(config, session_id=session_id, tool_registry=tool_registry)
    
    @classmethod
    def create_main_agent(cls, session_id: Optional[str] = None, tool_registry: Optional[ToolRegistry] = None) -> BaseAgent:
        """
        Create the main orchestrator agent (Claude Sonnet 4.5).
        
        Args:
            session_id: Optional session ID for token tracking
            tool_registry: Optional tool registry for agent tools
        """
        return cls.create_agent(
            agent_type=AgentType.CLAUDE_MAIN,
            agent_id="main_orchestrator",
            temperature=0.8,
            session_id=session_id,
            tool_registry=tool_registry
        )
    
    @classmethod
    def create_sub_agent(
        cls,
        agent_type: AgentType,
        task_description: Optional[str] = None,
        session_id: Optional[str] = None,
        tool_registry: Optional[ToolRegistry] = None
    ) -> BaseAgent:
        """
        Create a sub-agent for a specific task.
        
        Args:
            agent_type: Type of sub-agent to create
            task_description: Optional description to customize the system prompt
            session_id: Optional session ID for token tracking
            tool_registry: Optional tool registry for agent tools
            
        Returns:
            Configured sub-agent
        """
        custom_prompt = None
        if task_description:
            base_prompt = cls.SYSTEM_PROMPTS.get(agent_type, "")
            custom_prompt = f"{base_prompt}\n\nCurrent task: {task_description}"
        
        return cls.create_agent(
            agent_type=agent_type,
            custom_system_prompt=custom_prompt,
            temperature=0.7,
            session_id=session_id,
            tool_registry=tool_registry
        )

