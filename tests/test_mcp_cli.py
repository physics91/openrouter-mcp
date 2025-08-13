#!/usr/bin/env python3
"""
Tests for MCP CLI management commands.

This module tests the functionality of the Claude Code CLI MCP server management system,
including adding, removing, listing, and configuring MCP servers.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import sys

# Add the parent directory to the system path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.openrouter_mcp.cli.mcp_manager import (
    MCPManager,
    MCPServerConfig,
    MCPServerNotFoundError,
    MCPServerAlreadyExistsError,
    MCPConfigError
)


class TestMCPServerConfig:
    """Test MCPServerConfig data class."""
    
    def test_server_config_creation(self):
        """Test creating a server configuration."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"],
            cwd="/path/to/project",
            env={"OPENROUTER_API_KEY": "test-key"}
        )
        
        assert config.name == "openrouter"
        assert config.command == "python"
        assert config.args == ["-m", "src.openrouter_mcp.server"]
        assert config.cwd == "/path/to/project"
        assert config.env["OPENROUTER_API_KEY"] == "test-key"
    
    def test_server_config_to_dict(self):
        """Test converting server config to dictionary."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"]
        )
        
        config_dict = config.to_dict()
        assert "command" in config_dict
        assert "args" in config_dict
        assert config_dict["command"] == "python"
        assert config_dict["args"] == ["-m", "src.openrouter_mcp.server"]
    
    def test_server_config_from_dict(self):
        """Test creating server config from dictionary."""
        data = {
            "command": "node",
            "args": ["server.js"],
            "cwd": "/project",
            "env": {"API_KEY": "secret"}
        }
        
        config = MCPServerConfig.from_dict("test-server", data)
        assert config.name == "test-server"
        assert config.command == "node"
        assert config.args == ["server.js"]
        assert config.cwd == "/project"
        assert config.env["API_KEY"] == "secret"


class TestMCPManager:
    """Test MCPManager class."""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"mcpServers": {}}, f)
            temp_path = f.name
        
        yield Path(temp_path)
        
        # Cleanup
        if Path(temp_path).exists():
            os.unlink(temp_path)
    
    @pytest.fixture
    def manager(self, temp_config_file):
        """Create an MCPManager instance with a temporary config file."""
        return MCPManager(config_path=temp_config_file)
    
    def test_manager_initialization(self, manager, temp_config_file):
        """Test MCPManager initialization."""
        assert manager.config_path == temp_config_file
        assert manager.config == {"mcpServers": {}}
    
    def test_add_mcp_server_success(self, manager):
        """Test successfully adding an MCP server."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"],
            cwd=str(Path.cwd()),
            env={"OPENROUTER_API_KEY": "test-key"}
        )
        
        manager.add_server(config)
        
        assert "openrouter" in manager.config["mcpServers"]
        assert manager.config["mcpServers"]["openrouter"]["command"] == "python"
    
    def test_add_duplicate_server_error(self, manager):
        """Test adding a duplicate server raises an error."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"]
        )
        
        manager.add_server(config)
        
        with pytest.raises(MCPServerAlreadyExistsError):
            manager.add_server(config)
    
    def test_remove_mcp_server_success(self, manager):
        """Test successfully removing an MCP server."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"]
        )
        
        manager.add_server(config)
        manager.remove_server("openrouter")
        
        assert "openrouter" not in manager.config["mcpServers"]
    
    def test_remove_nonexistent_server_error(self, manager):
        """Test removing a non-existent server raises an error."""
        with pytest.raises(MCPServerNotFoundError):
            manager.remove_server("nonexistent")
    
    def test_list_installed_servers(self, manager):
        """Test listing installed MCP servers."""
        config1 = MCPServerConfig(name="server1", command="python", args=["s1.py"])
        config2 = MCPServerConfig(name="server2", command="node", args=["s2.js"])
        
        manager.add_server(config1)
        manager.add_server(config2)
        
        servers = manager.list_servers()
        assert len(servers) == 2
        assert "server1" in servers
        assert "server2" in servers
    
    def test_update_server_config(self, manager):
        """Test updating an existing server configuration."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"],
            env={"OPENROUTER_API_KEY": "old-key"}
        )
        
        manager.add_server(config)
        
        updated_config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"],
            env={"OPENROUTER_API_KEY": "new-key"}
        )
        
        manager.update_server(updated_config)
        
        assert manager.config["mcpServers"]["openrouter"]["env"]["OPENROUTER_API_KEY"] == "new-key"
    
    def test_validate_server_compatibility(self, manager):
        """Test validating server compatibility."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"]
        )
        
        # This should not raise an exception
        assert manager.validate_server(config) is True
    
    def test_handle_duplicate_server(self, manager):
        """Test handling duplicate server with force option."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "old.server"]
        )
        
        manager.add_server(config)
        
        new_config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "new.server"]
        )
        
        # Should replace with force=True
        manager.add_server(new_config, force=True)
        assert manager.config["mcpServers"]["openrouter"]["args"] == ["-m", "new.server"]
    
    def test_server_not_found_error(self, manager):
        """Test server not found error handling."""
        with pytest.raises(MCPServerNotFoundError) as exc_info:
            manager.get_server("nonexistent")
        
        assert "nonexistent" in str(exc_info.value)
    
    def test_get_server_status(self, manager):
        """Test getting server status."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"]
        )
        
        manager.add_server(config)
        status = manager.get_server_status("openrouter")
        
        assert status["name"] == "openrouter"
        assert status["installed"] is True
        assert "command" in status
        assert "args" in status
    
    def test_backup_config(self, manager, temp_config_file):
        """Test creating a backup of the configuration."""
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"]
        )
        
        manager.add_server(config)
        backup_path = manager.backup_config()
        
        assert backup_path.exists()
        assert backup_path.suffix == ".backup"
        
        # Cleanup
        if backup_path.exists():
            os.unlink(backup_path)
    
    def test_restore_config(self, manager, temp_config_file):
        """Test restoring configuration from backup."""
        # Add initial config
        config = MCPServerConfig(
            name="openrouter",
            command="python",
            args=["-m", "src.openrouter_mcp.server"]
        )
        manager.add_server(config)
        
        # Create backup
        backup_path = manager.backup_config()
        
        # Modify config
        manager.remove_server("openrouter")
        assert "openrouter" not in manager.config["mcpServers"]
        
        # Restore from backup
        manager.restore_config(backup_path)
        assert "openrouter" in manager.config["mcpServers"]
        
        # Cleanup
        if backup_path.exists():
            os.unlink(backup_path)
    
    def test_add_server_from_preset(self, manager):
        """Test adding a server from a preset configuration."""
        preset = manager.add_server_from_preset("openrouter", api_key="test-key")
        
        assert "openrouter" in manager.config["mcpServers"]
        assert manager.config["mcpServers"]["openrouter"]["env"]["OPENROUTER_API_KEY"] == "test-key"
    
    def test_save_config_error_handling(self, manager):
        """Test error handling when saving configuration fails."""
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(MCPConfigError) as exc_info:
                manager.save_config()
            
            assert "Failed to save configuration" in str(exc_info.value)
    
    def test_load_config_with_invalid_json(self, temp_config_file):
        """Test loading invalid JSON configuration."""
        # Write invalid JSON
        with open(temp_config_file, 'w') as f:
            f.write("{ invalid json }")
        
        with pytest.raises(MCPConfigError) as exc_info:
            MCPManager(config_path=temp_config_file)
        
        assert "Invalid configuration file" in str(exc_info.value)
    
    def test_cross_platform_paths(self, manager):
        """Test handling cross-platform paths correctly."""
        import platform
        
        config = MCPServerConfig(
            name="test",
            command="python",
            args=["-m", "module"],
            cwd="~/project" if platform.system() != "Windows" else "C:\\project"
        )
        
        manager.add_server(config)
        saved_config = manager.get_server("test")
        
        # Path should be properly expanded
        assert saved_config.cwd is not None
        if platform.system() != "Windows":
            assert not saved_config.cwd.startswith("~")


class TestCLIIntegration:
    """Test CLI command integration."""
    
    @pytest.fixture
    def cli_runner(self):
        """Create a CLI test runner."""
        from unittest.mock import MagicMock
        runner = MagicMock()
        return runner
    
    def test_claude_mcp_add_command(self, cli_runner):
        """Test 'claude mcp add openrouter' command."""
        from src.openrouter_mcp.cli.commands import add_mcp_server
        
        with patch('src.openrouter_mcp.cli.commands.MCPManager') as MockManager:
            # Mock the PRESETS class attribute
            MockManager.PRESETS = {"openrouter": {}}
            mock_manager = MockManager.return_value
            mock_manager.add_server_from_preset.return_value = True
            
            result = add_mcp_server("openrouter", api_key="test-key")
            
            assert result is True
            mock_manager.add_server_from_preset.assert_called_once_with(
                "openrouter", 
                api_key="test-key",
                force=False
            )
    
    def test_claude_mcp_remove_command(self, cli_runner):
        """Test 'claude mcp remove openrouter' command."""
        from src.openrouter_mcp.cli.commands import remove_mcp_server
        
        with patch('src.openrouter_mcp.cli.commands.MCPManager') as MockManager:
            mock_manager = MockManager.return_value
            
            result = remove_mcp_server("openrouter")
            
            assert result is True
            mock_manager.remove_server.assert_called_once_with("openrouter")
    
    def test_claude_mcp_list_command(self, cli_runner):
        """Test 'claude mcp list' command."""
        from src.openrouter_mcp.cli.commands import list_mcp_servers
        
        with patch('src.openrouter_mcp.cli.commands.MCPManager') as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.list_servers.return_value = ["server1", "server2"]
            
            servers = list_mcp_servers()
            
            assert len(servers) == 2
            assert "server1" in servers
            assert "server2" in servers
    
    def test_claude_mcp_status_command(self, cli_runner):
        """Test 'claude mcp status openrouter' command."""
        from src.openrouter_mcp.cli.commands import get_mcp_server_status
        
        with patch('src.openrouter_mcp.cli.commands.MCPManager') as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.get_server_status.return_value = {
                "name": "openrouter",
                "installed": True,
                "command": "python",
                "args": [],
                "cwd": None,
                "env": {},
                "config_path": "/path/to/config"
            }
            
            status = get_mcp_server_status("openrouter")
            
            assert status["name"] == "openrouter"
            assert status["installed"] is True
    
    def test_claude_mcp_config_command(self, cli_runner):
        """Test 'claude mcp config openrouter' command."""
        from src.openrouter_mcp.cli.commands import configure_mcp_server
        
        with patch('src.openrouter_mcp.cli.commands.MCPManager') as MockManager:
            mock_manager = MockManager.return_value
            
            result = configure_mcp_server(
                "openrouter",
                env={"OPENROUTER_API_KEY": "new-key"}
            )
            
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])