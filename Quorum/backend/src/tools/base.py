"""
Base tool interface for agent tools.
All tools should inherit from BaseTool and implement the execute method.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ToolResult(BaseModel):
    """Result from a tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class ToolParameter(BaseModel):
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


class BaseTool(ABC):
    """
    Base class for all agent tools.
    Tools provide additional capabilities to agents beyond text generation.
    """
    
    def __init__(self):
        """Initialize the tool."""
        self._name = self.name
        self._description = self.description
        self._parameters = self.parameters
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for the tool."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """List of parameters the tool accepts."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with success status and data
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get OpenAI function calling compatible schema for this tool.
        
        Returns:
            Dictionary in OpenAI function format
        """
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            
            properties[param.name] = prop
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    
    def validate_parameters(self, **kwargs) -> tuple[bool, Optional[str]]:
        """
        Validate that required parameters are provided.
        
        Args:
            **kwargs: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"
            
            if param.name in kwargs and param.enum:
                if kwargs[param.name] not in param.enum:
                    return False, f"Invalid value for {param.name}. Must be one of {param.enum}"
        
        return True, None

