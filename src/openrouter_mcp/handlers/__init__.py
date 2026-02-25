"""
Handlers package for OpenRouter MCP Server.

This package contains all the MCP tool handlers that provide OpenRouter API functionality.

All handlers import the shared MCP instance from mcp_registry to prevent duplicate
tool registration. Importing these modules triggers the @mcp.tool() decorators which
register the tools with the shared FastMCP instance.
"""

# Import all handlers to trigger tool registration
from . import chat
from . import multimodal
from . import mcp_benchmark
from . import collective_intelligence
from . import free_chat

__all__ = [
    "chat",
    "multimodal",
    "mcp_benchmark",
    "collective_intelligence",
    "free_chat",
]