#!/usr/bin/env python3
"""
MCP Server Manager for Claude Code CLI.

This module provides the core functionality for managing MCP servers
in the Claude Code CLI configuration.
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import platform
import logging

logger = logging.getLogger(__name__)


# Custom Exceptions
class MCPConfigError(Exception):
    """Base exception for MCP configuration errors."""
    pass


class MCPServerNotFoundError(MCPConfigError):
    """Raised when an MCP server is not found."""
    pass


class MCPServerAlreadyExistsError(MCPConfigError):
    """Raised when trying to add a server that already exists."""
    pass


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format for JSON."""
        config = {
            "command": self.command,
            "args": self.args
        }
        
        if self.cwd:
            config["cwd"] = self.cwd
        
        if self.env:
            config["env"] = self.env
        
        return config
    
    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'MCPServerConfig':
        """Create configuration from dictionary."""
        return cls(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            cwd=data.get("cwd"),
            env=data.get("env", {})
        )


class MCPManager:
    """Manager for MCP server configurations in Claude Code CLI."""
    
    # Default config paths for different platforms
    DEFAULT_CONFIG_PATHS = {
        "Windows": Path.home() / ".claude" / "claude_code_config.json",
        "Darwin": Path.home() / ".claude" / "claude_code_config.json",  # macOS
        "Linux": Path.home() / ".claude" / "claude_code_config.json"
    }
    
    # Preset configurations for common MCP servers
    PRESETS = {
        "openrouter": {
            "command": "cmd" if sys.platform == "win32" else "npx",
            "args": ["/c", "npx", "@physics91/openrouter-mcp"] if sys.platform == "win32" else ["@physics91/openrouter-mcp"],
            "env": {
                "OPENROUTER_API_KEY": None,  # Will be set by user
                "OPENROUTER_APP_NAME": "claude-code-mcp",
                "OPENROUTER_HTTP_REFERER": "https://localhost:3000",
                "HOST": "localhost",
                "PORT": "8000",
                "LOG_LEVEL": "info"
            },
            "description": "OpenRouter API client for multiple AI models via NPX"
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem"]
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"]
        },
        "memory": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"]
        }
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the MCP Manager.
        
        Args:
            config_path: Optional path to the configuration file.
                        If not provided, uses the default for the current platform.
        """
        if config_path is None:
            system = platform.system()
            config_path = self.DEFAULT_CONFIG_PATHS.get(
                system,
                self.DEFAULT_CONFIG_PATHS["Linux"]
            )
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not self.config_path.exists():
            # Create default config if file doesn't exist
            self._ensure_config_dir()
            default_config = {"mcpServers": {}}
            self._save_config(default_config)
            return default_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Ensure mcpServers key exists
            if "mcpServers" not in config:
                config["mcpServers"] = {}
            
            return config
            
        except json.JSONDecodeError as e:
            raise MCPConfigError(f"Invalid configuration file: {e}")
        except Exception as e:
            raise MCPConfigError(f"Failed to load configuration: {e}")
    
    def _save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration to file."""
        if config is None:
            config = self.config
        
        try:
            self._ensure_config_dir()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            raise MCPConfigError(f"Failed to save configuration: {e}")
    
    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        config_dir = self.config_path.parent
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
    
    def save_config(self) -> None:
        """Public method to save current configuration."""
        self._save_config()
    
    def add_server(self, config: MCPServerConfig, force: bool = False) -> None:
        """Add an MCP server to the configuration.
        
        Args:
            config: Server configuration to add
            force: If True, overwrites existing server with the same name
        
        Raises:
            MCPServerAlreadyExistsError: If server already exists and force is False
        """
        if config.name in self.config["mcpServers"] and not force:
            raise MCPServerAlreadyExistsError(
                f"Server '{config.name}' already exists. Use force=True to overwrite."
            )
        
        # Expand paths if needed
        if config.cwd:
            config.cwd = str(Path(config.cwd).expanduser().resolve())
        
        self.config["mcpServers"][config.name] = config.to_dict()
        self._save_config()
        
        logger.info(f"Added MCP server: {config.name}")
    
    def remove_server(self, name: str) -> None:
        """Remove an MCP server from the configuration.
        
        Args:
            name: Name of the server to remove
        
        Raises:
            MCPServerNotFoundError: If server doesn't exist
        """
        if name not in self.config["mcpServers"]:
            raise MCPServerNotFoundError(f"Server '{name}' not found")
        
        del self.config["mcpServers"][name]
        self._save_config()
        
        logger.info(f"Removed MCP server: {name}")
    
    def update_server(self, config: MCPServerConfig) -> None:
        """Update an existing MCP server configuration.
        
        Args:
            config: Updated server configuration
        
        Raises:
            MCPServerNotFoundError: If server doesn't exist
        """
        if config.name not in self.config["mcpServers"]:
            raise MCPServerNotFoundError(f"Server '{config.name}' not found")
        
        # Expand paths if needed
        if config.cwd:
            config.cwd = str(Path(config.cwd).expanduser().resolve())
        
        self.config["mcpServers"][config.name] = config.to_dict()
        self._save_config()
        
        logger.info(f"Updated MCP server: {config.name}")
    
    def get_server(self, name: str) -> MCPServerConfig:
        """Get a server configuration by name.
        
        Args:
            name: Name of the server
        
        Returns:
            Server configuration
        
        Raises:
            MCPServerNotFoundError: If server doesn't exist
        """
        if name not in self.config["mcpServers"]:
            raise MCPServerNotFoundError(f"Server '{name}' not found")
        
        return MCPServerConfig.from_dict(name, self.config["mcpServers"][name])
    
    def list_servers(self) -> List[str]:
        """List all installed MCP servers.
        
        Returns:
            List of server names
        """
        return list(self.config["mcpServers"].keys())
    
    def get_server_status(self, name: str) -> Dict[str, Any]:
        """Get detailed status of an MCP server.
        
        Args:
            name: Name of the server
        
        Returns:
            Dictionary with server status information
        
        Raises:
            MCPServerNotFoundError: If server doesn't exist
        """
        config = self.get_server(name)
        
        return {
            "name": config.name,
            "installed": True,
            "command": config.command,
            "args": config.args,
            "cwd": config.cwd,
            "env": config.env,
            "config_path": str(self.config_path)
        }
    
    def validate_server(self, config: MCPServerConfig) -> bool:
        """Validate server configuration.
        
        Args:
            config: Server configuration to validate
        
        Returns:
            True if configuration is valid
        
        Raises:
            MCPConfigError: If configuration is invalid
        """
        if not config.name:
            raise MCPConfigError("Server name is required")
        
        if not config.command:
            raise MCPConfigError("Server command is required")
        
        # Check if command exists (basic validation)
        if config.command in ["python", "node", "npx", "npm", "dotnet", "java"]:
            # Common commands are assumed to be valid
            return True
        
        # For absolute paths, check if file exists
        command_path = Path(config.command)
        if command_path.is_absolute() and not command_path.exists():
            raise MCPConfigError(f"Command not found: {config.command}")
        
        return True
    
    def backup_config(self) -> Path:
        """Create a backup of the current configuration.
        
        Returns:
            Path to the backup file
        """
        import time
        # Use timestamp with microseconds to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Add a small counter to ensure uniqueness
        counter = 0
        while True:
            if counter == 0:
                backup_filename = f"{self.config_path.stem}.{timestamp}.backup"
            else:
                backup_filename = f"{self.config_path.stem}.{timestamp}_{counter}.backup"
            backup_path = self.config_path.parent / backup_filename
            
            # Check if file already exists
            if not backup_path.exists():
                break
            counter += 1
            if counter > 100:
                # Safety check to avoid infinite loop
                raise MCPConfigError("Unable to create unique backup filename")
        
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Created configuration backup: {backup_path}")
        
        return backup_path
    
    def restore_config(self, backup_path: Path) -> None:
        """Restore configuration from a backup.
        
        Args:
            backup_path: Path to the backup file
        
        Raises:
            MCPConfigError: If backup file doesn't exist or is invalid
        """
        if not backup_path.exists():
            raise MCPConfigError(f"Backup file not found: {backup_path}")
        
        try:
            # Validate backup file
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_config = json.load(f)
            
            if "mcpServers" not in backup_config:
                raise MCPConfigError("Invalid backup file: missing mcpServers")
            
            # Create current backup before restoring
            current_backup = self.backup_config()
            
            try:
                # Restore from backup
                shutil.copy2(backup_path, self.config_path)
                # Reload configuration after restore
                self.config = self._load_config()
                
                logger.info(f"Restored configuration from: {backup_path}")
            except Exception as restore_error:
                # If restore fails, try to rollback
                if current_backup.exists():
                    shutil.copy2(current_backup, self.config_path)
                    self.config = self._load_config()
                raise MCPConfigError(f"Failed to restore, rolled back: {restore_error}")
            
        except json.JSONDecodeError:
            raise MCPConfigError("Invalid backup file: not valid JSON")
        except MCPConfigError:
            raise
        except Exception as e:
            raise MCPConfigError(f"Failed to restore configuration: {e}")
    
    def add_server_from_preset(self, preset_name: str, **kwargs) -> bool:
        """Add a server using a preset configuration.
        
        Args:
            preset_name: Name of the preset (e.g., 'openrouter', 'filesystem')
            **kwargs: Additional parameters for the preset (e.g., api_key)
        
        Returns:
            True if server was added successfully
        
        Raises:
            MCPConfigError: If preset doesn't exist
        """
        if preset_name not in self.PRESETS:
            available = ", ".join(self.PRESETS.keys())
            raise MCPConfigError(
                f"Unknown preset '{preset_name}'. Available presets: {available}"
            )
        
        preset = self.PRESETS[preset_name].copy()
        
        # Handle special parameters for specific presets
        if preset_name == "openrouter":
            if "api_key" in kwargs:
                if "env" not in preset:
                    preset["env"] = {}
                preset["env"]["OPENROUTER_API_KEY"] = kwargs["api_key"]
            
            # Set CWD to current OpenRouter project directory
            preset["cwd"] = str(Path(__file__).parent.parent.parent.parent.resolve())
        
        elif preset_name == "filesystem":
            # Add directory arguments if provided
            if "directories" in kwargs:
                preset["args"].extend(kwargs["directories"])
        
        elif preset_name == "github":
            if "token" in kwargs:
                if "env" not in preset:
                    preset["env"] = {}
                preset["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] = kwargs["token"]
        
        # Create server config from preset
        config = MCPServerConfig(
            name=preset_name,
            command=preset["command"],
            args=preset.get("args", []),
            cwd=preset.get("cwd"),
            env=preset.get("env", {})
        )
        
        # Add the server
        self.add_server(config, force=kwargs.get("force", False))
        
        return True