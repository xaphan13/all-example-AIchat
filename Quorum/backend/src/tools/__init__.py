"""
Tools module for AI agents.
Provides a registry system and various tools like web search.
"""
from src.tools.base import BaseTool, ToolResult
from src.tools.registry import ToolRegistry
from src.tools.web_search import WebSearchTool

__all__ = ["BaseTool", "ToolResult", "ToolRegistry", "WebSearchTool"]

