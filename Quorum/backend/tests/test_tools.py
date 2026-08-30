"""
Tests for the tool system including BaseTool, ToolRegistry, and WebSearchTool.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List
from datetime import datetime

from src.tools.base import BaseTool, ToolResult, ToolParameter
from src.tools.registry import ToolRegistry, get_tool_registry
from src.tools.web_search import WebSearchTool, create_web_search_tool


# ============================================================================
# Test Fixtures
# ============================================================================

class MockTool(BaseTool):
    """Mock tool for testing BaseTool functionality."""
    
    @property
    def name(self) -> str:
        return "mock_tool"
    
    @property
    def description(self) -> str:
        return "A mock tool for testing"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="text",
                type="string",
                description="Text input",
                required=True
            ),
            ToolParameter(
                name="count",
                type="number",
                description="Count parameter",
                required=False,
                default=1
            ),
            ToolParameter(
                name="mode",
                type="string",
                description="Mode parameter",
                required=False,
                default="normal",
                enum=["normal", "advanced"]
            )
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the mock tool."""
        return ToolResult(
            success=True,
            data={"message": "Mock execution", "params": kwargs}
        )


class FailingTool(BaseTool):
    """Tool that always fails for testing error handling."""
    
    @property
    def name(self) -> str:
        return "failing_tool"
    
    @property
    def description(self) -> str:
        return "A tool that fails"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return []
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the failing tool."""
        raise Exception("Tool execution failed")


@pytest.fixture
def mock_tool():
    """Create a mock tool instance."""
    return MockTool()


@pytest.fixture
def failing_tool():
    """Create a failing tool instance."""
    return FailingTool()


@pytest.fixture
def tool_registry():
    """Create a fresh tool registry for each test."""
    registry = ToolRegistry()
    return registry


# ============================================================================
# BaseTool Tests
# ============================================================================

class TestBaseTool:
    """Tests for BaseTool base class."""
    
    def test_tool_initialization(self, mock_tool):
        """Test that tool initializes with correct properties."""
        assert mock_tool.name == "mock_tool"
        assert mock_tool.description == "A mock tool for testing"
        assert len(mock_tool.parameters) == 3
    
    def test_get_schema(self, mock_tool):
        """Test OpenAI function schema generation."""
        schema = mock_tool.get_schema()
        
        assert schema["name"] == "mock_tool"
        assert schema["description"] == "A mock tool for testing"
        assert "parameters" in schema
        assert schema["parameters"]["type"] == "object"
        
        properties = schema["parameters"]["properties"]
        assert "text" in properties
        assert "count" in properties
        assert "mode" in properties
        
        assert properties["text"]["type"] == "string"
        assert properties["count"]["type"] == "number"
        assert properties["mode"]["enum"] == ["normal", "advanced"]
        
        required = schema["parameters"]["required"]
        assert "text" in required
        assert "count" not in required
        assert "mode" not in required
    
    def test_validate_parameters_success(self, mock_tool):
        """Test parameter validation with valid parameters."""
        is_valid, error = mock_tool.validate_parameters(
            text="test",
            count=5,
            mode="normal"
        )
        assert is_valid is True
        assert error is None
    
    def test_validate_parameters_missing_required(self, mock_tool):
        """Test parameter validation with missing required parameter."""
        is_valid, error = mock_tool.validate_parameters(count=5)
        assert is_valid is False
        assert "Missing required parameter: text" in error
    
    def test_validate_parameters_invalid_enum(self, mock_tool):
        """Test parameter validation with invalid enum value."""
        is_valid, error = mock_tool.validate_parameters(
            text="test",
            mode="invalid"
        )
        assert is_valid is False
        assert "Invalid value for mode" in error
    
    def test_validate_parameters_with_defaults(self, mock_tool):
        """Test that validation passes with only required params."""
        is_valid, error = mock_tool.validate_parameters(text="test")
        assert is_valid is True
        assert error is None
    
    @pytest.mark.asyncio
    async def test_execute(self, mock_tool):
        """Test tool execution."""
        result = await mock_tool.execute(text="test", count=3)
        
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data["message"] == "Mock execution"
        assert result.data["params"]["text"] == "test"
        assert result.data["params"]["count"] == 3


# ============================================================================
# ToolRegistry Tests
# ============================================================================

class TestToolRegistry:
    """Tests for ToolRegistry."""
    
    def test_registry_initialization(self, tool_registry):
        """Test that registry initializes empty."""
        assert len(tool_registry.list_tools()) == 0
    
    def test_register_tool(self, tool_registry, mock_tool):
        """Test tool registration."""
        tool_registry.register(mock_tool)
        
        assert "mock_tool" in tool_registry.list_tools()
        assert tool_registry.get_tool("mock_tool") == mock_tool
    
    def test_register_duplicate_tool(self, tool_registry, mock_tool):
        """Test that registering duplicate tool overwrites."""
        tool_registry.register(mock_tool)
        tool_registry.register(mock_tool)
        
        # Should still only have one tool
        assert len(tool_registry.list_tools()) == 1
    
    def test_unregister_tool(self, tool_registry, mock_tool):
        """Test tool unregistration."""
        tool_registry.register(mock_tool)
        result = tool_registry.unregister("mock_tool")
        
        assert result is True
        assert "mock_tool" not in tool_registry.list_tools()
    
    def test_unregister_nonexistent_tool(self, tool_registry):
        """Test unregistering tool that doesn't exist."""
        result = tool_registry.unregister("nonexistent")
        assert result is False
    
    def test_get_tool(self, tool_registry, mock_tool):
        """Test getting a tool by name."""
        tool_registry.register(mock_tool)
        retrieved = tool_registry.get_tool("mock_tool")
        
        assert retrieved == mock_tool
    
    def test_get_nonexistent_tool(self, tool_registry):
        """Test getting a tool that doesn't exist."""
        retrieved = tool_registry.get_tool("nonexistent")
        assert retrieved is None
    
    def test_list_tools(self, tool_registry, mock_tool, failing_tool):
        """Test listing all registered tools."""
        tool_registry.register(mock_tool)
        tool_registry.register(failing_tool)
        
        tools = tool_registry.list_tools()
        assert len(tools) == 2
        assert "mock_tool" in tools
        assert "failing_tool" in tools
    
    def test_get_all_schemas(self, tool_registry, mock_tool, failing_tool):
        """Test getting schemas for all tools."""
        tool_registry.register(mock_tool)
        tool_registry.register(failing_tool)
        
        schemas = tool_registry.get_all_schemas()
        assert len(schemas) == 2
        assert any(s["name"] == "mock_tool" for s in schemas)
        assert any(s["name"] == "failing_tool" for s in schemas)
    
    @pytest.mark.asyncio
    async def test_execute_tool_success(self, tool_registry, mock_tool):
        """Test successful tool execution through registry."""
        tool_registry.register(mock_tool)
        
        result = await tool_registry.execute_tool("mock_tool", text="test")
        
        assert result.success is True
        assert result.data["message"] == "Mock execution"
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, tool_registry):
        """Test executing a tool that doesn't exist."""
        result = await tool_registry.execute_tool("nonexistent")
        
        assert result.success is False
        assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_execute_tool_validation_failure(self, tool_registry, mock_tool):
        """Test executing tool with invalid parameters."""
        tool_registry.register(mock_tool)
        
        # Missing required parameter
        result = await tool_registry.execute_tool("mock_tool", count=5)
        
        assert result.success is False
        assert "validation failed" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_execute_tool_execution_error(self, tool_registry, failing_tool):
        """Test handling of tool execution errors."""
        tool_registry.register(failing_tool)
        
        result = await tool_registry.execute_tool("failing_tool")
        
        assert result.success is False
        assert "execution failed" in result.error.lower()
    
    def test_clear_registry(self, tool_registry, mock_tool, failing_tool):
        """Test clearing all tools from registry."""
        tool_registry.register(mock_tool)
        tool_registry.register(failing_tool)
        
        tool_registry.clear()
        
        assert len(tool_registry.list_tools()) == 0
    
    def test_global_registry_singleton(self):
        """Test that get_tool_registry returns same instance."""
        registry1 = get_tool_registry()
        registry2 = get_tool_registry()
        
        assert registry1 is registry2


# ============================================================================
# WebSearchTool Tests
# ============================================================================

class TestWebSearchTool:
    """Tests for WebSearchTool."""
    
    def test_web_search_tool_initialization(self):
        """Test WebSearchTool initialization."""
        tool = WebSearchTool(provider="duckduckgo")
        
        assert tool.name == "web_search"
        assert tool.provider == "duckduckgo"
        assert "search the internet" in tool.description.lower()
    
    def test_web_search_tool_parameters(self):
        """Test WebSearchTool parameters."""
        tool = WebSearchTool()
        params = tool.parameters
        
        param_names = [p.name for p in params]
        assert "query" in param_names
        assert "num_results" in param_names
        assert "search_type" in param_names
        
        # Check query is required
        query_param = next(p for p in params if p.name == "query")
        assert query_param.required is True
    
    def test_web_search_tool_schema(self):
        """Test WebSearchTool OpenAI schema."""
        tool = WebSearchTool()
        schema = tool.get_schema()
        
        assert schema["name"] == "web_search"
        assert "query" in schema["parameters"]["properties"]
        assert "query" in schema["parameters"]["required"]
    
    @pytest.mark.asyncio
    async def test_web_search_duckduckgo_success(self):
        """Test successful DuckDuckGo search."""
        tool = WebSearchTool(provider="duckduckgo")
        
        # Mock the DDGS class
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {
                "title": "Test Result 1",
                "href": "https://example.com/1",
                "body": "Test snippet 1"
            },
            {
                "title": "Test Result 2",
                "href": "https://example.com/2",
                "body": "Test snippet 2"
            }
        ]
        
        # Create a mock module
        mock_ddgs_module = MagicMock()
        mock_ddgs_module.DDGS = MagicMock(return_value=mock_ddgs_instance)
        
        with patch.dict('sys.modules', {'duckduckgo_search': mock_ddgs_module}):
            result = await tool.execute(query="test query", num_results=2)
        
        assert result.success is True
        assert result.data["query"] == "test query"
        assert result.data["provider"] == "duckduckgo"
        assert len(result.data["results"]) == 2
        assert result.data["results"][0]["title"] == "Test Result 1"
        assert result.data["results"][0]["url"] == "https://example.com/1"
    
    @pytest.mark.asyncio
    async def test_web_search_duckduckgo_news(self):
        """Test DuckDuckGo news search."""
        tool = WebSearchTool(provider="duckduckgo")
        
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.news.return_value = [
            {
                "title": "News Article",
                "url": "https://news.example.com",
                "body": "News snippet",
                "source": "Example News"
            }
        ]
        
        mock_ddgs_module = MagicMock()
        mock_ddgs_module.DDGS = MagicMock(return_value=mock_ddgs_instance)
        
        with patch.dict('sys.modules', {'duckduckgo_search': mock_ddgs_module}):
            result = await tool.execute(
                query="news query",
                num_results=1,
                search_type="news"
            )
        
        assert result.success is True
        assert result.metadata["search_type"] == "news"
        assert mock_ddgs_instance.news.called
    
    @pytest.mark.asyncio
    async def test_web_search_duckduckgo_images(self):
        """Test DuckDuckGo image search."""
        tool = WebSearchTool(provider="duckduckgo")
        
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.images.return_value = [
            {
                "title": "Image Result",
                "image": "https://example.com/image.jpg",
                "thumbnail": "https://example.com/thumb.jpg",
                "source": "Example"
            }
        ]
        
        mock_ddgs_module = MagicMock()
        mock_ddgs_module.DDGS = MagicMock(return_value=mock_ddgs_instance)
        
        with patch.dict('sys.modules', {'duckduckgo_search': mock_ddgs_module}):
            result = await tool.execute(
                query="image query",
                search_type="images"
            )
        
        assert result.success is True
        assert result.metadata["search_type"] == "images"
        assert mock_ddgs_instance.images.called
    
    @pytest.mark.asyncio
    async def test_web_search_num_results_clamping(self):
        """Test that num_results is clamped to valid range."""
        tool = WebSearchTool(provider="duckduckgo")
        
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = []
        
        mock_ddgs_module = MagicMock()
        mock_ddgs_module.DDGS = MagicMock(return_value=mock_ddgs_instance)
        
        with patch.dict('sys.modules', {'duckduckgo_search': mock_ddgs_module}):
            # Test too high
            await tool.execute(query="test", num_results=100)
            call_args = mock_ddgs_instance.text.call_args
            assert call_args[1]["max_results"] == 10
            
            # Test too low
            await tool.execute(query="test", num_results=-5)
            call_args = mock_ddgs_instance.text.call_args
            assert call_args[1]["max_results"] == 1
    
    @pytest.mark.asyncio
    async def test_web_search_missing_duckduckgo_library(self):
        """Test error handling when duckduckgo-search is not installed."""
        tool = WebSearchTool(provider="duckduckgo")
        
        # Don't patch sys.modules - let the ImportError happen naturally
        # Remove duckduckgo_search from sys.modules if it exists
        with patch.dict('sys.modules', {'duckduckgo_search': None}):
            result = await tool.execute(query="test")
        
        assert result.success is False
        assert "failed" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_web_search_invalid_provider(self):
        """Test error handling for invalid provider."""
        tool = WebSearchTool(provider="invalid_provider")
        
        result = await tool.execute(query="test")
        
        assert result.success is False
        assert "unsupported" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_web_search_tavily_no_api_key(self):
        """Test Tavily search without API key."""
        tool = WebSearchTool(provider="tavily", api_key=None)
        
        # Make sure env var is not set
        with patch.dict('os.environ', {}, clear=True):
            result = await tool.execute(query="test")
        
        assert result.success is False
        assert "api key" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_web_search_serpapi_no_api_key(self):
        """Test SerpAPI search without API key."""
        tool = WebSearchTool(provider="serpapi", api_key=None)
        
        with patch.dict('os.environ', {}, clear=True):
            result = await tool.execute(query="test")
        
        assert result.success is False
        assert "api key" in result.error.lower()
    
    def test_create_web_search_tool_factory(self):
        """Test factory function for creating web search tool."""
        tool = create_web_search_tool(provider="duckduckgo")
        
        assert isinstance(tool, WebSearchTool)
        assert tool.provider == "duckduckgo"
    
    @pytest.mark.asyncio
    async def test_web_search_exception_handling(self):
        """Test general exception handling in execute."""
        tool = WebSearchTool(provider="duckduckgo")
        
        # Mock DDGS to raise an exception
        mock_ddgs_module = MagicMock()
        mock_ddgs_module.DDGS = MagicMock(side_effect=Exception("Network error"))
        
        with patch.dict('sys.modules', {'duckduckgo_search': mock_ddgs_module}):
            result = await tool.execute(query="test")
        
        assert result.success is False
        assert "failed" in result.error.lower()


# ============================================================================
# Integration Tests
# ============================================================================

class TestToolIntegration:
    """Integration tests for the tool system."""
    
    @pytest.mark.asyncio
    async def test_register_and_execute_web_search(self):
        """Test registering and executing web search through registry."""
        registry = ToolRegistry()
        tool = WebSearchTool(provider="duckduckgo")
        registry.register(tool)
        
        # Mock DuckDuckGo
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {
                "title": "Integration Test",
                "href": "https://example.com",
                "body": "Test snippet"
            }
        ]
        
        mock_ddgs_module = MagicMock()
        mock_ddgs_module.DDGS = MagicMock(return_value=mock_ddgs_instance)
        
        with patch.dict('sys.modules', {'duckduckgo_search': mock_ddgs_module}):
            result = await registry.execute_tool(
                "web_search",
                query="integration test"
            )
        
        assert result.success is True
        assert result.data["query"] == "integration test"
        assert len(result.data["results"]) == 1
    
    @pytest.mark.asyncio
    async def test_multiple_tools_in_registry(self, mock_tool):
        """Test managing multiple tools in registry."""
        registry = ToolRegistry()
        registry.register(mock_tool)
        registry.register(WebSearchTool())
        
        tools = registry.list_tools()
        assert len(tools) == 2
        assert "mock_tool" in tools
        assert "web_search" in tools
        
        schemas = registry.get_all_schemas()
        assert len(schemas) == 2
    
    def test_tool_result_structure(self, mock_tool):
        """Test that ToolResult has proper structure."""
        result = ToolResult(
            success=True,
            data={"test": "data"},
            error=None,
            metadata={"key": "value"}
        )
        
        assert result.success is True
        assert result.data == {"test": "data"}
        assert result.error is None
        assert result.metadata == {"key": "value"}
        assert isinstance(result.timestamp, datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

