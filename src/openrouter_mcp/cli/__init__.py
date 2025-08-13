"""
Claude Code CLI MCP Management Module.

This module provides functionality for managing MCP servers through
the Claude Code CLI, including adding, removing, listing, and configuring servers.
"""

from .mcp_manager import (
    MCPManager,
    MCPServerConfig,
    MCPServerNotFoundError,
    MCPServerAlreadyExistsError,
    MCPConfigError
)

from .commands import (
    add_mcp_server,
    remove_mcp_server,
    list_mcp_servers,
    get_mcp_server_status,
    configure_mcp_server
)

__all__ = [
    # Manager classes
    'MCPManager',
    'MCPServerConfig',
    
    # Exceptions
    'MCPServerNotFoundError',
    'MCPServerAlreadyExistsError',
    'MCPConfigError',
    
    # CLI commands
    'add_mcp_server',
    'remove_mcp_server',
    'list_mcp_servers',
    'get_mcp_server_status',
    'configure_mcp_server',
]