#!/usr/bin/env python3
"""
CLI Commands for MCP Server Management.

This module provides the command-line interface functions for managing
MCP servers in Claude Code CLI.
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import click
import json

from .mcp_manager import (
    MCPManager,
    MCPServerConfig,
    MCPServerNotFoundError,
    MCPServerAlreadyExistsError,
    MCPConfigError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Simple format for CLI output
)
logger = logging.getLogger(__name__)


def add_mcp_server(
    server_name: str,
    api_key: Optional[str] = None,
    force: bool = False,
    **kwargs
) -> bool:
    """Add an MCP server to Claude Code CLI.
    
    Args:
        server_name: Name of the server or preset
        api_key: API key for servers that require it
        force: Force overwrite if server exists
        **kwargs: Additional server-specific parameters
    
    Returns:
        True if successful
    """
    try:
        manager = MCPManager()
        
        # Check if it's a preset
        if server_name in MCPManager.PRESETS or not kwargs.get('command'):
            # Try as preset first
            if server_name in MCPManager.PRESETS:
                success = manager.add_server_from_preset(
                    server_name,
                    api_key=api_key,
                    force=force,
                    **kwargs
                )
                if success:
                    click.echo(f"✅ Successfully added MCP server: {server_name}")
                    
                    # Show post-installation instructions
                    if server_name == "openrouter":
                        click.echo("\n📝 Next steps:")
                        click.echo("1. Restart Claude Code CLI")
                        click.echo("2. The OpenRouter MCP tools will be available")
                        click.echo("\nExample commands:")
                        click.echo("  - 'list available models'")
                        click.echo("  - 'compare gpt-4 and claude-3'")
                    
                    return True
            else:
                # Not a preset and no command provided
                click.echo(f"❌ Error: '{server_name}' is not a known preset. Custom servers require a 'command' parameter.")
                click.echo(f"Available presets: {', '.join(MCPManager.PRESETS.keys())}")
                return False
        else:
            # Custom server configuration with command provided
            config = MCPServerConfig(
                name=server_name,
                command=kwargs.get("command"),
                args=kwargs.get("args", []),
                cwd=kwargs.get("cwd"),
                env=kwargs.get("env", {})
            )
            
            manager.add_server(config, force=force)
            click.echo(f"✅ Successfully added MCP server: {server_name}")
            return True
            
    except MCPServerAlreadyExistsError:
        click.echo(f"⚠️ Server '{server_name}' already exists. Use --force to overwrite.")
        return False
    except MCPConfigError as e:
        click.echo(f"❌ Configuration error: {e}")
        return False
    except Exception as e:
        click.echo(f"❌ Failed to add server: {e}")
        logger.exception("Error adding MCP server")
        return False


def remove_mcp_server(server_name: str) -> bool:
    """Remove an MCP server from Claude Code CLI.
    
    Args:
        server_name: Name of the server to remove
    
    Returns:
        True if successful
    """
    try:
        manager = MCPManager()
        manager.remove_server(server_name)
        click.echo(f"✅ Successfully removed MCP server: {server_name}")
        return True
        
    except MCPServerNotFoundError:
        click.echo(f"❌ Server '{server_name}' not found")
        return False
    except Exception as e:
        click.echo(f"❌ Failed to remove server: {e}")
        logger.exception("Error removing MCP server")
        return False


def list_mcp_servers(verbose: bool = False) -> List[str]:
    """List all installed MCP servers.
    
    Args:
        verbose: Show detailed information
    
    Returns:
        List of server names
    """
    try:
        manager = MCPManager()
        servers = manager.list_servers()
        
        if not servers:
            click.echo("No MCP servers installed.")
            click.echo("\nAvailable presets:")
            for preset in MCPManager.PRESETS.keys():
                click.echo(f"  - {preset}")
            click.echo("\nUse 'claude mcp add <preset-name>' to install a server.")
            return []
        
        click.echo("📋 Installed MCP servers:")
        for server in servers:
            if verbose:
                status = manager.get_server_status(server)
                click.echo(f"\n🔹 {server}")
                click.echo(f"   Command: {status['command']}")
                if status['args']:
                    click.echo(f"   Args: {' '.join(status['args'])}")
                if status['cwd']:
                    click.echo(f"   Working Dir: {status['cwd']}")
                if status['env']:
                    click.echo(f"   Environment: {len(status['env'])} variables")
            else:
                click.echo(f"  - {server}")
        
        return servers
        
    except Exception as e:
        click.echo(f"❌ Failed to list servers: {e}")
        logger.exception("Error listing MCP servers")
        return []


def get_mcp_server_status(server_name: str) -> Dict[str, Any]:
    """Get status of an MCP server.
    
    Args:
        server_name: Name of the server
    
    Returns:
        Server status dictionary
    """
    try:
        manager = MCPManager()
        status = manager.get_server_status(server_name)
        
        click.echo(f"📊 Status for MCP server: {server_name}")
        click.echo(f"  Installed: {'✅ Yes' if status['installed'] else '❌ No'}")
        click.echo(f"  Command: {status['command']}")
        
        if status.get('args'):
            click.echo(f"  Arguments: {' '.join(status['args'])}")
        
        if status.get('cwd'):
            click.echo(f"  Working Directory: {status['cwd']}")
        
        if status.get('env'):
            click.echo(f"  Environment Variables:")
            for key in status['env'].keys():
                if 'KEY' in key or 'TOKEN' in key:
                    click.echo(f"    - {key}: ***")
                else:
                    click.echo(f"    - {key}: {status['env'][key]}")
        
        click.echo(f"  Config File: {status['config_path']}")
        
        return status
        
    except MCPServerNotFoundError:
        click.echo(f"❌ Server '{server_name}' not found")
        return {}
    except Exception as e:
        click.echo(f"❌ Failed to get server status: {e}")
        logger.exception("Error getting MCP server status")
        return {}


def configure_mcp_server(
    server_name: str,
    env: Optional[Dict[str, str]] = None,
    args: Optional[List[str]] = None,
    cwd: Optional[str] = None
) -> bool:
    """Configure an existing MCP server.
    
    Args:
        server_name: Name of the server to configure
        env: Environment variables to update
        args: Command arguments to update
        cwd: Working directory to update
    
    Returns:
        True if successful
    """
    try:
        manager = MCPManager()
        
        # Get existing configuration
        config = manager.get_server(server_name)
        
        # Update configuration
        if env:
            config.env.update(env)
        
        if args is not None:
            config.args = args
        
        if cwd is not None:
            config.cwd = cwd
        
        # Save updated configuration
        manager.update_server(config)
        
        click.echo(f"✅ Successfully updated configuration for: {server_name}")
        return True
        
    except MCPServerNotFoundError:
        click.echo(f"❌ Server '{server_name}' not found")
        return False
    except Exception as e:
        click.echo(f"❌ Failed to configure server: {e}")
        logger.exception("Error configuring MCP server")
        return False


# CLI Command Group
@click.group()
def mcp():
    """Manage MCP servers for Claude Code CLI."""
    pass


@mcp.command()
@click.argument('server_name')
@click.option('--api-key', help='API key for the server')
@click.option('--force', is_flag=True, help='Force overwrite existing server')
@click.option('--command', help='Command to run the server')
@click.option('--args', multiple=True, help='Arguments for the server command')
@click.option('--cwd', help='Working directory for the server')
@click.option('--env', multiple=True, help='Environment variables (KEY=VALUE format)')
def add(server_name, api_key, force, command, args, cwd, env):
    """Add an MCP server to Claude Code CLI."""
    env_dict = {}
    if env:
        for env_var in env:
            if '=' in env_var:
                key, value = env_var.split('=', 1)
                env_dict[key] = value
    
    kwargs = {}
    if command:
        kwargs['command'] = command
    if args:
        kwargs['args'] = list(args)
    if cwd:
        kwargs['cwd'] = cwd
    if env_dict:
        kwargs['env'] = env_dict
    
    add_mcp_server(server_name, api_key=api_key, force=force, **kwargs)


@mcp.command()
@click.argument('server_name')
def remove(server_name):
    """Remove an MCP server from Claude Code CLI."""
    remove_mcp_server(server_name)


@mcp.command('list')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def list_cmd(verbose):
    """List all installed MCP servers."""
    list_mcp_servers(verbose=verbose)


@mcp.command()
@click.argument('server_name')
def status(server_name):
    """Get status of an MCP server."""
    get_mcp_server_status(server_name)


@mcp.command()
@click.argument('server_name')
@click.option('--env', multiple=True, help='Environment variables (KEY=VALUE format)')
@click.option('--args', multiple=True, help='New arguments for the server')
@click.option('--cwd', help='New working directory')
def config(server_name, env, args, cwd):
    """Configure an existing MCP server."""
    env_dict = {}
    if env:
        for env_var in env:
            if '=' in env_var:
                key, value = env_var.split('=', 1)
                env_dict[key] = value
    
    args_list = list(args) if args else None
    
    configure_mcp_server(
        server_name,
        env=env_dict if env_dict else None,
        args=args_list,
        cwd=cwd
    )


if __name__ == "__main__":
    # For testing: Allow running as a module
    if len(sys.argv) > 1:
        mcp()