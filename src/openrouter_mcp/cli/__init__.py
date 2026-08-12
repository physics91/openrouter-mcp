"""
Claude Code CLI MCP Management Module.

This module provides functionality for managing MCP servers through
the Claude Code CLI, including adding, removing, listing, and configuring servers.
"""

from .commands import (
    add_mcp_server,
    configure_mcp_server,
    get_mcp_server_status,
    list_mcp_servers,
    remove_mcp_server,
)
from .mcp_manager import (
    MCPConfigError,
    MCPManager,
    MCPServerAlreadyExistsError,
    MCPServerConfig,
    MCPServerNotFoundError,
)

__all__ = [
    "MCPConfigError",
    "MCPManager",
    "MCPServerAlreadyExistsError",
    "MCPServerConfig",
    "MCPServerNotFoundError",
    "add_mcp_server",
    "configure_mcp_server",
    "get_mcp_server_status",
    "list_mcp_servers",
    "remove_mcp_server",
]
