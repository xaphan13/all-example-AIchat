"""
Example usage of the tool registry with web search capabilities.
Demonstrates how to register tools and use them with agents.
"""
import asyncio
import os
from src.agents.agent_factory import AgentFactory
from src.core.models import AgentType
from src.tools.registry import ToolRegistry, get_tool_registry
from src.tools.web_search import WebSearchTool


async def basic_web_search_example():
    """Example: Basic web search using DuckDuckGo (no API key needed)."""
    print("=" * 60)
    print("Example 1: Basic Web Search with DuckDuckGo")
    print("=" * 60)
    
    # Create tool registry
    registry = ToolRegistry()
    
    # Create and register web search tool (DuckDuckGo by default)
    web_search = WebSearchTool(provider="duckduckgo")
    registry.register(web_search)
    
    # Create agent with tool registry
    agent = AgentFactory.create_agent(
        agent_type=AgentType.CLAUDE_MAIN,
        tool_registry=registry
    )
    
    print(f"Agent created with {len(registry.list_tools())} tools")
    print(f"Available tools: {registry.list_tools()}")
    
    # Execute a search
    print("\nSearching for 'latest AI developments 2024'...")
    result = await agent.execute_tool(
        "web_search",
        query="latest AI developments 2024",
        num_results=3
    )
    
    if result.success:
        print(f"\nFound {result.data['count']} results:")
        for i, item in enumerate(result.data['results'], 1):
            print(f"\n{i}. {item['title']}")
            print(f"   URL: {item['url']}")
            print(f"   Snippet: {item['snippet'][:100]}...")
    else:
        print(f"Search failed: {result.error}")


async def agent_with_tools_example():
    """Example: Agent conversation with web search capability."""
    print("\n" + "=" * 60)
    print("Example 2: Agent Conversation with Web Search")
    print("=" * 60)
    
    # Setup registry with tools
    registry = ToolRegistry()
    registry.register(WebSearchTool(provider="duckduckgo"))
    
    # Create agent
    agent = AgentFactory.create_main_agent(tool_registry=registry)
    
    # Prepare messages with system prompt that mentions tools
    messages = [
        {
            "role": "system",
            "content": """You are a helpful assistant with access to web search.
When you need current information, you can use the web_search tool.
The tool accepts: query (string), num_results (1-10), and search_type ('general', 'news', 'images')."""
        },
        {
            "role": "user",
            "content": "What are the latest developments in quantum computing?"
        }
    ]
    
    print("\nAgent responding (this demonstrates tool awareness)...")
    response = await agent.get_complete_response(messages)
    print(f"\nAgent response:\n{response}")


async def multiple_searches_example():
    """Example: Multiple searches with different types."""
    print("\n" + "=" * 60)
    print("Example 3: Multiple Search Types")
    print("=" * 60)
    
    registry = ToolRegistry()
    registry.register(WebSearchTool(provider="duckduckgo"))
    
    agent = AgentFactory.create_agent(
        agent_type=AgentType.GPT5,
        tool_registry=registry
    )
    
    # General search
    print("\n1. General Search:")
    result = await agent.execute_tool(
        "web_search",
        query="Python programming best practices",
        num_results=2,
        search_type="general"
    )
    if result.success:
        for item in result.data['results']:
            print(f"   - {item['title']}")
    
    # News search
    print("\n2. News Search:")
    result = await agent.execute_tool(
        "web_search",
        query="technology news today",
        num_results=2,
        search_type="news"
    )
    if result.success:
        for item in result.data['results']:
            print(f"   - {item['title']}")


async def tool_registry_management():
    """Example: Managing the tool registry."""
    print("\n" + "=" * 60)
    print("Example 4: Tool Registry Management")
    print("=" * 60)
    
    # Create registry
    registry = ToolRegistry()
    
    print(f"Initial tools: {registry.list_tools()}")
    
    # Register tools
    web_search = WebSearchTool(provider="duckduckgo")
    registry.register(web_search)
    
    print(f"After registration: {registry.list_tools()}")
    
    # Get tool schemas (for LLM function calling)
    schemas = registry.get_all_schemas()
    print(f"\nTool schemas: {len(schemas)} tools")
    for schema in schemas:
        print(f"\nTool: {schema['name']}")
        print(f"Description: {schema['description'][:80]}...")
        print(f"Parameters: {list(schema['parameters']['properties'].keys())}")
    
    # Unregister tool
    registry.unregister("web_search")
    print(f"\nAfter unregister: {registry.list_tools()}")


async def global_registry_example():
    """Example: Using the global registry singleton."""
    print("\n" + "=" * 60)
    print("Example 5: Global Registry Singleton")
    print("=" * 60)
    
    # Get global registry (shared across application)
    registry = get_tool_registry()
    
    # Register tools once
    registry.register(WebSearchTool(provider="duckduckgo"))
    
    print(f"Global registry tools: {registry.list_tools()}")
    
    # Create multiple agents that share the same registry
    agent1 = AgentFactory.create_agent(
        agent_type=AgentType.CLAUDE_MAIN,
        tool_registry=registry
    )
    
    agent2 = AgentFactory.create_agent(
        agent_type=AgentType.GPT5,
        tool_registry=registry
    )
    
    print(f"Agent 1 tools: {agent1.get_tool_registry().list_tools()}")
    print(f"Agent 2 tools: {agent2.get_tool_registry().list_tools()}")
    
    # Both agents can use the same tools
    result = await agent1.execute_tool(
        "web_search",
        query="machine learning trends",
        num_results=1
    )
    print(f"\nAgent 1 search success: {result.success}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Tool Registry & Web Search Examples")
    print("=" * 60)
    
    try:
        await basic_web_search_example()
        await agent_with_tools_example()
        await multiple_searches_example()
        await tool_registry_management()
        await global_registry_example()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

