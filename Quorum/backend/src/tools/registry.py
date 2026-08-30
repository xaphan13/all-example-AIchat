"""
Tool registry for managing available tools for agents.
Provides centralized registration and lookup of tools.
"""
from typing import Dict, List, Optional, Any
from src.tools.base import BaseTool, ToolResult
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """
    Central registry for managing tools available to agents.
    Supports tool registration, lookup, and execution.
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, BaseTool] = {}
        logger.info("tool_registry_initialized")
    
    def register(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool: Tool instance to register
        """
        if tool.name in self._tools:
            logger.warning(
                "tool_already_registered",
                tool_name=tool.name,
                message="Overwriting existing tool"
            )
        
        self._tools[tool.name] = tool
        logger.info(
            "tool_registered",
            tool_name=tool.name,
            description=tool.description
        )
    
    def unregister(self, tool_name: str) -> bool:
        """
        Unregister a tool from the registry.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Returns:
            True if tool was unregistered, False if not found
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info("tool_unregistered", tool_name=tool_name)
            return True
        return False
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """
        Get OpenAI function schemas for all registered tools.
        
        Returns:
            List of tool schemas in OpenAI function format
        """
        return [tool.get_schema() for tool in self._tools.values()]
    
    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution result
        """
        tool = self.get_tool(tool_name)
        
        if not tool:
            logger.error("tool_not_found", tool_name=tool_name)
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found in registry"
            )
        
        # Validate parameters
        is_valid, error_msg = tool.validate_parameters(**kwargs)
        if not is_valid:
            logger.error(
                "tool_parameter_validation_failed",
                tool_name=tool_name,
                error=error_msg
            )
            return ToolResult(
                success=False,
                error=f"Parameter validation failed: {error_msg}"
            )
        
        # Execute the tool
        try:
            logger.debug(
                "tool_execution_started",
                tool_name=tool_name,
                parameters=kwargs
            )
            result = await tool.execute(**kwargs)
            logger.info(
                "tool_execution_completed",
                tool_name=tool_name,
                success=result.success
            )
            return result
        except Exception as e:
            logger.error(
                "tool_execution_error",
                tool_name=tool_name,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}"
            )
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        logger.info("tool_registry_cleared")


# Global registry instance
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance (singleton).
    
    Returns:
        Global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry

