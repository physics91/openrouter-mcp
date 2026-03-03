# Claude Desktop Integration Guide

This guide walks you through integrating OpenRouter MCP Server with Claude Desktop, giving you access to 100+ AI models directly within Claude's interface.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Setup (Automated)](#quick-setup-automated)
- [Manual Setup](#manual-setup)
- [Verification](#verification)
- [Using OpenRouter Tools](#using-openrouter-tools)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Prerequisites

Before starting, ensure you have:

1. **Claude Desktop App** installed
   - Download from: [claude.ai/desktop](https://claude.ai/desktop)
   - Available for macOS, Windows, and Linux

2. **OpenRouter API Key**
   - Sign up at: [openrouter.ai](https://openrouter.ai)
   - Get your API key from the dashboard

3. **OpenRouter MCP Server** installed
   ```bash
   npm install -g openrouter-mcp
   # or use npx for one-time usage
   ```

## Quick Setup (Automated)

The easiest way to set up Claude Desktop integration:

### Step 1: Initialize OpenRouter MCP

```bash
npx openrouter-mcp init
```

This will prompt you for:
- Your OpenRouter API key
- App name (optional)
- HTTP referer (optional)

### Step 2: Install Claude Desktop Configuration

```bash
npx openrouter-mcp install-claude
```

This automatically:
- Detects your operating system
- Finds the correct Claude Desktop config path
- Updates the configuration file
- Preserves existing MCP servers

### Step 3: Restart Claude Desktop

Close and reopen Claude Desktop to load the new configuration.

## Manual Setup

If you prefer manual configuration or the automated setup doesn't work:

### Step 1: Locate Claude Desktop Config File

The configuration file location depends on your operating system:

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%/Claude/claude_desktop_config.json
```

**Linux:**
```
~/.config/claude/claude_desktop_config.json
```

### Step 2: Create or Edit Configuration

If the file doesn't exist, create it. If it exists, add to the existing `mcpServers` section:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "your-openrouter-api-key-here"
      }
    }
  }
}
```

### Step 3: Complete Example Configuration

Here's a complete configuration file with multiple MCP servers:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-xxx...",
        "OPENROUTER_APP_NAME": "claude-desktop",
        "OPENROUTER_HTTP_REFERER": "https://claude.ai"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"]
    }
  }
}
```

### Step 4: Save and Restart

1. Save the configuration file
2. Close Claude Desktop completely
3. Reopen Claude Desktop

## Verification

### Check if Integration Worked

After restarting Claude Desktop:

1. **Look for the tool icon** (🔧) in the Claude Desktop interface
2. **Check available tools** - you should see OpenRouter tools listed
3. **Test a simple command**:
   ```
   List available AI models using OpenRouter
   ```

### Status Check via CLI

You can also verify the server status:

```bash
npx openrouter-mcp status
```

This shows:
- Python environment status
- API key configuration
- Dependencies status
- Configuration file location

## Using OpenRouter Tools

Once integrated, you can use these commands with Claude:

### 1. Chat with Different Models

```
Use GPT-4 to explain quantum computing in simple terms
```

```
Have Claude Opus write a creative story about time travel
```

```
Ask Llama 2 to review this code for potential improvements
```

### 2. Compare Models

```
List all available GPT models and their pricing
```

```
Show me the cheapest models for text generation
```

```
Compare pricing between OpenAI and Anthropic models
```

### 3. Track Usage

```
Show my API usage for this month
```

```
What's my total cost so far today?
```

```
Which models have I used most frequently?
```

### Available Models

Popular models you can access:

**OpenAI Models:**
- `openai/gpt-4` - Most capable GPT-4
- `openai/gpt-4-turbo` - Faster GPT-4 variant
- `openai/gpt-3.5-turbo` - Fast and economical

**Anthropic Models:**
- `anthropic/claude-3-opus` - Most capable Claude
- `anthropic/claude-3-sonnet` - Balanced capability/speed
- `anthropic/claude-3-haiku` - Fast and efficient

**Open Source Models:**
- `meta-llama/llama-2-70b-chat` - Meta's flagship
- `mistralai/mixtral-8x7b-instruct` - Efficient expert model
- `microsoft/wizardlm-2-8x22b` - Instruction following

## Troubleshooting

### Common Issues and Solutions

#### 1. Claude Desktop Not Showing Tools

**Symptoms:** No tool icon appears, tools not available

**Solutions:**
- Verify config file location and format
- Check JSON syntax (use JSONLint)
- Ensure Claude Desktop was fully restarted
- Check config file permissions

**Debug steps:**
```bash
# Check config file exists
ls -la "~/Library/Application Support/Claude/claude_desktop_config.json"  # macOS
dir "%APPDATA%\Claude\claude_desktop_config.json"  # Windows

# Validate JSON format
python -m json.tool claude_desktop_config.json

# Check server status
npx openrouter-mcp status
```

#### 2. Authentication Errors

**Symptoms:** "Invalid API key" or authentication errors

**Solutions:**
- Verify API key is correct and active
- Check environment variable spelling
- Ensure no extra spaces in API key
- Test API key directly with OpenRouter

**Debug steps:**
```bash
# Test API key
curl -H "Authorization: Bearer your-api-key" https://openrouter.ai/api/v1/models

# Re-initialize if needed
npx openrouter-mcp init
```

#### 3. Server Won't Start

**Symptoms:** MCP server fails to launch

**Solutions:**
- Check Python installation
- Install missing dependencies
- Verify port availability
- Check system permissions

**Debug steps:**
```bash
# Check Python
python --version

# Install dependencies
pip install -r requirements.txt

# Test manual start
npx openrouter-mcp start --debug
```

#### 4. Tools Not Working

**Symptoms:** Tools appear but fail when used

**Solutions:**
- Check network connectivity
- Verify OpenRouter service status
- Review tool parameters
- Check rate limits

**Debug steps:**
```bash
# Check OpenRouter status
curl https://openrouter.ai/api/v1/models

# Test with simple request
npx openrouter-mcp start --verbose
```

### Log Analysis

Enable debug logging for detailed troubleshooting:

```bash
npx openrouter-mcp start --debug
```

Logs will show:
- Server startup process
- API request/response details
- Error stack traces
- Performance metrics

### Getting Help

If issues persist:

1. **Check the logs** with debug mode enabled
2. **Verify your configuration** against examples
3. **Test components individually** (Python, Node.js, API key)
4. **Create an issue** with logs and configuration details

## Advanced Configuration

### Custom Server Settings

You can customize the server behavior with environment variables:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start", "--port", "9000"],
      "env": {
        "OPENROUTER_API_KEY": "your-key",
        "OPENROUTER_APP_NAME": "my-custom-app",
        "OPENROUTER_HTTP_REFERER": "https://my-domain.com",
        "LOG_LEVEL": "debug",
        "HOST": "127.0.0.1",
        "PORT": "9000"
      }
    }
  }
}
```

### Multiple OpenRouter Configurations

You can run multiple OpenRouter instances with different configurations:

```json
{
  "mcpServers": {
    "openrouter-main": {
      "command": "npx",
      "args": ["openrouter-mcp", "start", "--port", "8000"],
      "env": {
        "OPENROUTER_API_KEY": "your-main-key"
      }
    },
    "openrouter-experimental": {
      "command": "npx", 
      "args": ["openrouter-mcp", "start", "--port", "8001"],
      "env": {
        "OPENROUTER_API_KEY": "your-experimental-key"
      }
    }
  }
}
```

### Performance Tuning

For high-volume usage:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "your-key",
        "LOG_LEVEL": "warning",
        "WORKER_PROCESSES": "4",
        "REQUEST_TIMEOUT": "300"
      }
    }
  }
}
```

### Security Considerations

For production use:

1. **Store API keys securely**
   - Use environment variables
   - Avoid committing keys to version control
   - Rotate keys regularly

2. **Network security**
   - Bind to localhost only (default)
   - Use HTTPS in production
   - Implement rate limiting

3. **Access control**
   - Limit file system access
   - Monitor usage patterns
   - Set up alerts for unusual activity

### Integration with Other MCP Servers

OpenRouter MCP works well with other MCP servers:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/safe/path"]
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

This gives Claude access to:
- 100+ AI models (OpenRouter)
- File system operations
- Web search capabilities
- Persistent memory

---

## Next Steps

With OpenRouter MCP integrated into Claude Desktop, you can:

1. **Experiment with different models** for various tasks
2. **Compare model outputs** for the same prompt
3. **Track costs and usage** across models
4. **Build complex workflows** combining multiple AI models

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Complete setup instructions
- [API Documentation](API.md) - Available MCP tools
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Benchmarking Guide](BENCHMARK_GUIDE.md) - Model performance comparison
- [FAQ](FAQ.md) - Frequently asked questions

For a complete documentation overview, see the [Documentation Index](INDEX.md).

For more information:
- [Main README](../README.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [OpenRouter Documentation](https://openrouter.ai/docs)

---

**Last Updated**: 2025-01-12
**Version**: 1.4.0