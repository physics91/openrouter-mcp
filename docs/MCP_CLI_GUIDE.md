# Claude Code MCP CLI Management Guide

## Overview

The OpenRouter MCP Server now includes a powerful CLI management system for Claude Code, allowing you to easily add, remove, and configure MCP servers using simple commands.

## Installation

The MCP CLI management system is automatically included with the OpenRouter MCP Server installation.

## Usage

### Using the Standalone CLI

You can use the `claude_mcp.py` script directly:

```bash
python claude_mcp.py [COMMAND] [OPTIONS]
```

### Available Commands

#### 1. Add an MCP Server

Add a new MCP server using presets or custom configuration:

```bash
# Add OpenRouter server with API key
python claude_mcp.py add openrouter --api-key sk-or-your-key-here

# Add GitHub server with token
python claude_mcp.py add github --env GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx

# Add filesystem server with directories
python claude_mcp.py add filesystem --args /path/to/dir1 --args /path/to/dir2

# Add custom server
python claude_mcp.py add myserver --command python --args server.py --cwd /project
```

Options:
- `--api-key`: API key for servers that require authentication
- `--force`: Force overwrite if server already exists
- `--command`: Command to run the server (for custom servers)
- `--args`: Arguments for the server command (can be used multiple times)
- `--cwd`: Working directory for the server
- `--env`: Environment variables in KEY=VALUE format (can be used multiple times)

#### 2. List MCP Servers

List all installed MCP servers:

```bash
# Simple list
python claude_mcp.py list

# Verbose list with details
python claude_mcp.py list --verbose
```

#### 3. Get Server Status

Get detailed status of a specific MCP server:

```bash
python claude_mcp.py status openrouter
```

#### 4. Configure a Server

Update configuration for an existing MCP server:

```bash
# Update API key
python claude_mcp.py config openrouter --env OPENROUTER_API_KEY=new-key

# Update working directory
python claude_mcp.py config myserver --cwd /new/path

# Update arguments
python claude_mcp.py config filesystem --args /new/dir1 --args /new/dir2
```

#### 5. Remove a Server

Remove an MCP server from Claude Code:

```bash
python claude_mcp.py remove openrouter
```

## Available Presets

The following MCP servers are available as presets for easy installation:

### OpenRouter
Provides access to multiple AI models through OpenRouter's API.

```bash
python claude_mcp.py add openrouter --api-key YOUR_OPENROUTER_API_KEY
```

Required: OpenRouter API key from https://openrouter.ai

### Filesystem
Provides file system access to specified directories.

```bash
python claude_mcp.py add filesystem --args ~/Documents --args ~/Desktop
```

### GitHub
Provides GitHub repository access and management.

```bash
python claude_mcp.py add github --env GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx
```

Required: GitHub Personal Access Token

### Memory
Provides in-memory storage capabilities.

```bash
python claude_mcp.py add memory
```

## Integration with Claude Code

After adding MCP servers, restart Claude Code CLI to use the new tools. The configuration is automatically saved to:

- **Windows**: `%USERPROFILE%\.claude\claude_code_config.json`
- **macOS/Linux**: `~/.claude/claude_code_config.json`

## Configuration File Structure

The MCP servers are stored in the Claude Code configuration file:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "python",
      "args": ["-m", "src.openrouter_mcp.server"],
      "cwd": "/path/to/openrouter-mcp",
      "env": {
        "OPENROUTER_API_KEY": "sk-or-xxx",
        "HOST": "localhost",
        "PORT": "8000"
      }
    }
  }
}
```

## Python API

You can also use the MCP Manager programmatically:

```python
from src.openrouter_mcp.cli import MCPManager, MCPServerConfig

# Create manager
manager = MCPManager()

# Add a server
config = MCPServerConfig(
    name="myserver",
    command="python",
    args=["server.py"],
    env={"API_KEY": "secret"}
)
manager.add_server(config)

# List servers
servers = manager.list_servers()
print(f"Installed servers: {servers}")

# Get server status
status = manager.get_server_status("myserver")
print(f"Server status: {status}")

# Remove server
manager.remove_server("myserver")
```

## Troubleshooting

### Server Not Found
If you get a "server not found" error, check that:
1. The server name is correct
2. The server has been added (use `list` command)

### Permission Errors
If you encounter permission errors:
1. Ensure you have write access to the Claude config directory
2. Try running with appropriate permissions

### API Key Issues
For servers requiring API keys:
1. Ensure the API key is valid
2. Check that environment variables are set correctly
3. Use the `config` command to update keys

## Advanced Features

### Backup and Restore

The MCP Manager automatically creates backups when modifying configuration:

```python
from src.openrouter_mcp.cli import MCPManager

manager = MCPManager()

# Create manual backup
backup_path = manager.backup_config()
print(f"Backup created: {backup_path}")

# Restore from backup
manager.restore_config(backup_path)
```

### Cross-Platform Support

The MCP CLI automatically handles platform-specific paths and configurations:
- Windows paths are properly escaped
- Home directory expansion works on all platforms
- Environment variables are platform-appropriate

## Examples

### Complete Setup Example

```bash
# 1. Add OpenRouter server
python claude_mcp.py add openrouter --api-key sk-or-xxx

# 2. Add filesystem access to Desktop
python claude_mcp.py add filesystem --args ~/Desktop

# 3. List all servers
python claude_mcp.py list --verbose

# 4. Restart Claude Code CLI
# The MCP tools are now available!
```

### Using in Claude Code

After setup, you can use the MCP tools in Claude Code:

```
User: List available AI models
Claude: I'll list the available models using the OpenRouter MCP tool...

User: Read files from my Desktop
Claude: I'll access your Desktop using the filesystem MCP tool...
```

### Using Collective Intelligence Tools

The OpenRouter MCP Server includes 5 advanced collective intelligence tools for enhanced AI collaboration:

```bash
# Example: Multi-model consensus for complex decisions
User: "Use collective intelligence to analyze the pros and cons of remote work with 3 different models"
Claude: I'll use the collective_chat_completion tool to get consensus from multiple AI models...

# Example: Ensemble reasoning for complex problems
User: "Apply ensemble reasoning to design a sustainable energy solution for a small city"
Claude: I'll use ensemble_reasoning to decompose this complex problem and assign different aspects to specialized models...

# Example: Adaptive model selection for optimal performance
User: "Automatically select the best model for writing a Python function to process large datasets"
Claude: I'll use adaptive_model_selection to find the most suitable model for this coding task...

# Example: Cross-model validation for accuracy
User: "Validate this scientific statement across multiple models: 'Quantum computers will replace classical computers within 10 years'"
Claude: I'll use cross_model_validation to verify this claim across multiple AI models...

# Example: Collaborative problem solving
User: "Solve this business challenge collaboratively: How to reduce customer churn by 30% in 6 months"
Claude: I'll use collaborative_problem_solving to get multiple models working together on this challenge...
```

### Performance Benefits

The collective intelligence tools provide significant advantages:

- **Higher Accuracy**: Multi-model consensus reduces individual model biases
- **Better Quality**: Cross-validation ensures response reliability  
- **Optimal Performance**: Adaptive selection chooses the best model for each task
- **Complex Problem Solving**: Ensemble reasoning handles multi-faceted challenges
- **Reliability**: Collaborative approaches provide robust, well-reasoned solutions

## Support

For issues or questions:
1. Check the [OpenRouter MCP documentation](https://github.com/yourusername/openrouter-mcp)
2. Review the [Model Context Protocol specification](https://modelcontextprotocol.io)
3. File an issue on GitHub

## License

MIT License - See LICENSE file for details.