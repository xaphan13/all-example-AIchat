"""
Web search tool for agents using multiple search providers.
Supports DuckDuckGo (no API key), Tavily, and SerpAPI.
"""
import os
from typing import List, Optional, Dict, Any
import httpx
from src.tools.base import BaseTool, ToolResult, ToolParameter
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class WebSearchTool(BaseTool):
    """
    Web search tool that allows agents to search the internet.
    Supports multiple providers: DuckDuckGo (default), Tavily, SerpAPI.
    """
    
    def __init__(self, provider: str = "duckduckgo", api_key: Optional[str] = None):
        """
        Initialize web search tool.
        
        Args:
            provider: Search provider ("duckduckgo", "tavily", "serpapi")
            api_key: API key for the provider (not needed for DuckDuckGo)
        """
        self.provider = provider.lower()
        self.api_key = api_key
        
        # Get API key from environment if not provided
        if not self.api_key:
            if self.provider == "tavily":
                self.api_key = os.getenv("TAVILY_API_KEY")
            elif self.provider == "serpapi":
                self.api_key = os.getenv("SERPAPI_API_KEY")
        
        super().__init__()
        
        logger.info(
            "web_search_tool_initialized",
            provider=self.provider,
            has_api_key=bool(self.api_key)
        )
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return """Search the internet for current information. Use this tool when you need:
- Current events or news
- Recent data or statistics
- Real-time information
- Facts that may have changed since your training
- Information about specific websites or companies
Returns a list of relevant search results with titles, snippets, and URLs."""
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="The search query. Be specific and include relevant keywords.",
                required=True
            ),
            ToolParameter(
                name="num_results",
                type="number",
                description="Number of results to return (1-10)",
                required=False,
                default=5
            ),
            ToolParameter(
                name="search_type",
                type="string",
                description="Type of search: 'general', 'news', 'images'",
                required=False,
                default="general",
                enum=["general", "news", "images"]
            )
        ]
    
    async def execute(self, query: str, num_results: int = 5, search_type: str = "general", **kwargs) -> ToolResult:
        """
        Execute web search.
        
        Args:
            query: Search query
            num_results: Number of results to return
            search_type: Type of search
            
        Returns:
            ToolResult with search results
        """
        try:
            # Validate num_results
            num_results = max(1, min(10, num_results))
            
            logger.debug(
                "web_search_started",
                query=query,
                provider=self.provider,
                num_results=num_results,
                search_type=search_type
            )
            
            # Route to appropriate provider
            if self.provider == "duckduckgo":
                results = await self._search_duckduckgo(query, num_results, search_type)
            elif self.provider == "tavily":
                results = await self._search_tavily(query, num_results, search_type)
            elif self.provider == "serpapi":
                results = await self._search_serpapi(query, num_results, search_type)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unsupported search provider: {self.provider}"
                )
            
            logger.info(
                "web_search_completed",
                query=query,
                provider=self.provider,
                results_count=len(results)
            )
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "provider": self.provider,
                    "count": len(results)
                },
                metadata={
                    "search_type": search_type,
                    "num_results": num_results
                }
            )
            
        except Exception as e:
            logger.error(
                "web_search_error",
                query=query,
                provider=self.provider,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )
    
    async def _search_duckduckgo(self, query: str, num_results: int, search_type: str) -> List[Dict[str, Any]]:
        """
        Search using DuckDuckGo (no API key required).
        Uses the duckduckgo-search library.
        """
        try:
            from duckduckgo_search import DDGS
            
            ddgs = DDGS()
            results = []
            
            if search_type == "news":
                search_results = ddgs.news(query, max_results=num_results)
            elif search_type == "images":
                search_results = ddgs.images(query, max_results=num_results)
            else:
                search_results = ddgs.text(query, max_results=num_results)
            
            for result in search_results:
                if search_type == "images":
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("image", ""),
                        "thumbnail": result.get("thumbnail", ""),
                        "source": result.get("source", "")
                    })
                else:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("href", result.get("url", "")),
                        "snippet": result.get("body", result.get("description", "")),
                        "source": result.get("source", "")
                    })
            
            return results
            
        except ImportError:
            logger.error("duckduckgo_search_not_installed")
            raise Exception("duckduckgo-search library not installed. Run: pip install duckduckgo-search")
    
    async def _search_tavily(self, query: str, num_results: int, search_type: str) -> List[Dict[str, Any]]:
        """
        Search using Tavily API.
        """
        if not self.api_key:
            raise Exception("Tavily API key not found. Set TAVILY_API_KEY environment variable.")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": num_results,
                    "search_depth": "advanced" if search_type == "news" else "basic",
                    "include_images": search_type == "images",
                    "include_answer": True
                }
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for result in data.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", ""),
                    "score": result.get("score", 0)
                })
            
            return results
    
    async def _search_serpapi(self, query: str, num_results: int, search_type: str) -> List[Dict[str, Any]]:
        """
        Search using SerpAPI.
        """
        if not self.api_key:
            raise Exception("SerpAPI key not found. Set SERPAPI_API_KEY environment variable.")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "api_key": self.api_key,
                "q": query,
                "num": num_results,
                "engine": "google"
            }
            
            if search_type == "news":
                params["tbm"] = "nws"
            elif search_type == "images":
                params["tbm"] = "isch"
            
            response = await client.get(
                "https://serpapi.com/search",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            if search_type == "images":
                for result in data.get("images_results", [])[:num_results]:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("original", ""),
                        "thumbnail": result.get("thumbnail", ""),
                        "source": result.get("source", "")
                    })
            elif search_type == "news":
                for result in data.get("news_results", [])[:num_results]:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "snippet": result.get("snippet", ""),
                        "source": result.get("source", ""),
                        "date": result.get("date", "")
                    })
            else:
                for result in data.get("organic_results", [])[:num_results]:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "snippet": result.get("snippet", ""),
                        "position": result.get("position", 0)
                    })
            
            return results


def create_web_search_tool(provider: str = "duckduckgo", api_key: Optional[str] = None) -> WebSearchTool:
    """
    Factory function to create a web search tool.
    
    Args:
        provider: Search provider ("duckduckgo", "tavily", "serpapi")
        api_key: API key for the provider
        
    Returns:
        WebSearchTool instance
    """
    return WebSearchTool(provider=provider, api_key=api_key)

