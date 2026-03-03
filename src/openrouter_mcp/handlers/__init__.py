"""
Handlers package for OpenRouter MCP Server.

This package contains all the MCP tool handlers that provide OpenRouter API functionality.

All handlers import the shared MCP instance from mcp_registry to prevent duplicate
tool registration. Importing these modules triggers the @mcp.tool() decorators which
register the tools with the shared FastMCP instance.
"""

# Import all handlers to trigger tool registration
from . import chat, collective_intelligence, free_chat, mcp_benchmark, multimodal

__all__ = [
    "chat",
    "multimodal",
    "mcp_benchmark",
    "collective_intelligence",
    "free_chat",
]
