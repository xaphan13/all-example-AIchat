"""
Data models for the multi-agent communication system.
Defines the structure of messages, agents, tasks, and responses.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class AgentType(str, Enum):
    """Available agent types in the system."""
    CLAUDE_MAIN = "claude-sonnet-4.5"
    CLAUDE_SUB = "claude-sonnet-3.5"
    GPT5 = "gpt-5"


class AgentStatus(str, Enum):
    """Current status of an agent."""
    IDLE = "idle"
    THINKING = "thinking"
    RESPONDING = "responding"
    COMPLETE = "complete"
    ERROR = "error"


class Message(BaseModel):
    """A single message in the conversation."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        json_schema_serialization_defaults_required=True
    )
    
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    agent_id: Optional[str] = None


class AgentConfig(BaseModel):
    """Configuration for a specific agent."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    agent_id: str
    agent_type: AgentType
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: Optional[str] = None


class SubAgentQuery(BaseModel):
    """A query to be sent to a sub-agent."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    agent_type: AgentType
    query: str
    context: Optional[str] = None
    priority: int = 1


class AgentResponse(BaseModel):
    """Response from an agent."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    agent_id: str
    agent_type: AgentType
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    """A chunk of streaming data."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    agent_id: str
    content: str
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None


class TaskRequest(BaseModel):
    """A user request to be processed by the agent system."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    message: str
    conversation_id: Optional[str] = None
    max_sub_agents: int = 3
    enable_collaboration: bool = True


class TaskResponse(BaseModel):
    """Response from the task processing."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    conversation_id: str
    main_response: str
    sub_agent_responses: List[AgentResponse] = Field(default_factory=list)
    execution_time: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """Current state of an agent during execution."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    agent_id: str
    agent_type: AgentType
    status: AgentStatus
    current_message: Optional[str] = None
    progress: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class AgentMessage(BaseModel):
    """A message from one agent to another or to all agents."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    message_id: str
    from_agent_id: str
    from_agent_type: AgentType
    to_agent_id: Optional[str] = None  # None means broadcast to all
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    round_number: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationRound(BaseModel):
    """A round of conversation between agents."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    round_number: int
    messages: List[AgentMessage] = Field(default_factory=list)
    participating_agents: List[str] = Field(default_factory=list)
    is_complete: bool = False


class ConversationState(BaseModel):
    """Overall state of a conversation."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    conversation_id: str
    messages: List[Message] = Field(default_factory=list)
    active_agents: List[AgentState] = Field(default_factory=list)
    agent_conversations: List[ConversationRound] = Field(default_factory=list)
    is_complete: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class WebSocketMessage(BaseModel):
    """WebSocket message from client to server."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    type: str  # "subscribe", "unsubscribe", "task", "ping"
    conversation_id: Optional[str] = None
    task: Optional[TaskRequest] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

