# Claude Code CLI Integration Guide

This guide walks you through integrating OpenRouter MCP Server with Claude Code CLI so you can use OpenRouter models directly inside your terminal development workflow.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Setup (Automated)](#quick-setup-automated)
- [Manual Setup](#manual-setup)
- [Verification](#verification)
- [Using OpenRouter Tools in Claude Code](#using-openrouter-tools-in-claude-code)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Prerequisites

Before starting, ensure you have:

1. **Claude Code CLI** installed
   - Install via npm: `npm install -g @anthropic/claude-code`
   - Or download from: [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)

2. **OpenRouter API Key**
   - Sign up at: [openrouter.ai](https://openrouter.ai)
   - Get your API key from the dashboard

3. **OpenRouter MCP Server** installed
   ```bash
   npm install -g @physics91/openrouter-mcp
   # or use npx for one-time usage
   ```

## Quick Setup (Automated)

The easiest way to set up Claude Code CLI integration:

### Step 1: Initialize OpenRouter MCP

```bash
npx @physics91/openrouter-mcp@latest init
```

This will prompt you for:
- Your OpenRouter API key
- App name (optional)
- HTTP referer (optional)
- Integration choices (select "Claude Code CLI")

### Step 2: Alternative Direct Installation

If you already have configuration set up:

```bash
npx @physics91/openrouter-mcp@latest install-claude-code
```

This automatically:
- Detects Claude Code CLI installation
- Creates or updates the configuration file
- Configures the MCP server connection

## Manual Setup

If you prefer manual configuration:

### Step 1: Locate Claude Code CLI Config File

The configuration file is located at:

**All Platforms:**
```
~/.claude/claude_code_config.json
```

### Step 2: Create or Edit Configuration

If the file doesn't exist, create it. If it exists, add to the existing `mcpServers` section:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["@physics91/openrouter-mcp", "start"],
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
      "args": ["@physics91/openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-xxx...",
        "OPENROUTER_APP_NAME": "claude-code",
        "OPENROUTER_HTTP_REFERER": "https://localhost"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"]
    }
  }
}
```

### Step 4: Save Configuration

1. Save the configuration file
2. No restart required - Claude Code CLI will detect changes automatically

## Verification

### Check if Integration Worked

After configuration:

1. **Test with a simple command**:
   ```bash
   claude "List available AI models using OpenRouter"
   ```

2. **Check available tools**:
   ```bash
   claude "What tools do I have available?"
   ```

### Status Check via CLI

You can also verify the server status:

```bash
npx @physics91/openrouter-mcp@latest status
```

This shows:
- Claude Code CLI detection
- API key configuration
- Dependencies status
- Configuration file location

## Using OpenRouter Tools in Claude Code

Once integrated, you can use these commands with Claude Code CLI:

### 1. Interactive AI Model Selection

```bash
# Chat with different models
claude "Use GPT-4 to explain quantum computing"
claude "Have Claude Opus write a creative story"
claude "Ask Llama 2 to review this code file"
```

### 2. Model Discovery and Comparison

```bash
# Explore available models
claude "List all available GPT models and their pricing"
claude "Show me the cheapest models for code generation"
claude "Compare OpenAI and Anthropic model capabilities"
```

### 3. Development Workflow Integration

```bash
# Code analysis with different models
claude "Use multiple AI models to review my Python script"
claude "Compare code suggestions from GPT-4 and Claude Sonnet"

# Documentation and explanation
claude "Have different models explain this complex algorithm"
claude "Generate API documentation using the best model for technical writing"
```

### 4. Usage Tracking and Cost Management

```bash
# Monitor usage and costs
claude "Show my OpenRouter API usage for today"
claude "Which AI models am I using most frequently?"
claude "Calculate the cost difference between using GPT-4 vs Claude"
```

### Available Models

Popular models you can access through Claude Code:

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

#### 1. Claude Code CLI Not Detecting Tools

**Symptoms:** No OpenRouter tools available in Claude Code

**Solutions:**
- Verify Claude Code CLI installation: `claude --version`
- Check config file location and format
- Ensure JSON syntax is valid
- Verify file permissions

**Debug steps:**
```bash
# Check Claude Code CLI installation
claude --version

# Validate JSON configuration
python -c "import json; print(json.load(open('~/.claude/claude_code_config.json')))"

# Check server status
npx @physics91/openrouter-mcp@latest status
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
# Test API key directly
curl -H "Authorization: Bearer your-api-key" https://openrouter.ai/api/v1/models

# Re-initialize if needed
npx @physics91/openrouter-mcp@latest init
```

#### 3. Server Connection Issues

**Symptoms:** MCP server fails to start or connect

**Solutions:**
- Check Python installation and dependencies
- Verify network connectivity
- Review server logs for detailed errors
- Check port availability

**Debug steps:**
```bash
# Check Python environment
python --version
pip list | grep -E "(fastmcp|httpx|pydantic)"

# Test manual server start
npx @physics91/openrouter-mcp@latest start --verbose

# Check system resources
ps aux | grep openrouter-mcp
```

#### 4. Tools Not Working

**Symptoms:** Tools appear but fail when used

**Solutions:**
- Check OpenRouter service status
- Review tool parameters and usage
- Verify rate limits aren't exceeded
- Check network connectivity

### Advanced Debugging

Enable debug logging for detailed troubleshooting:

```bash
# Start with debug logging
npx @physics91/openrouter-mcp@latest start --debug

# Check configuration in detail
claude "Debug: Show me all available MCP tools and their status"
```

## Advanced Configuration

### Environment Variables

You can customize the server behavior with environment variables in the config:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["@physics91/openrouter-mcp", "start", "--port", "9000"],
      "env": {
        "OPENROUTER_API_KEY": "your-key",
        "OPENROUTER_APP_NAME": "claude-code-custom",
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
      "args": ["@physics91/openrouter-mcp", "start", "--port", "8000"],
      "env": {
        "OPENROUTER_API_KEY": "your-main-key"
      }
    },
    "openrouter-experimental": {
      "command": "npx",
      "args": ["@physics91/openrouter-mcp", "start", "--port", "8001"],
      "env": {
        "OPENROUTER_API_KEY": "your-experimental-key"
      }
    }
  }
}
```

### Development Workflow Integration

For development-focused usage:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["@physics91/openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "your-key",
        "OPENROUTER_APP_NAME": "dev-assistant",
        "LOG_LEVEL": "info"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/your/projects"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    }
  }
}
```

### Performance Optimization

For high-volume development usage:

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["@physics91/openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "your-key",
        "LOG_LEVEL": "warning",
        "WORKER_PROCESSES": "2",
        "REQUEST_TIMEOUT": "120"
      }
    }
  }
}
```

## Best Practices

### 1. Model Selection for Development

- **Code Review**: Use `anthropic/claude-3-sonnet` or `openai/gpt-4`
- **Quick Questions**: Use `openai/gpt-3.5-turbo` or `anthropic/claude-3-haiku`
- **Complex Analysis**: Use `openai/gpt-4` or `anthropic/claude-3-opus`
- **Cost Optimization**: Use `mistralai/mixtral-8x7b-instruct`

### 2. Workflow Integration

```bash
# Morning development routine
claude "Show me my OpenRouter usage for yesterday"
claude "List the most cost-effective models for code review"

# During development
claude "Use Claude Sonnet to review this function for bugs"
claude "Have GPT-4 explain this complex algorithm"
claude "Compare different models' suggestions for optimizing this code"

# End of day
claude "Summarize my AI model usage today"
claude "Calculate costs for my development assistant usage"
```

### 3. Security Considerations

1. **API Key Management**
   - Use environment variables when possible
   - Avoid committing keys to version control
   - Rotate keys regularly

2. **Access Control**
   - Limit filesystem access in MCP configuration
   - Monitor usage patterns
   - Set up alerts for unusual activity

## Integration with Other Tools

### VS Code Integration

While Claude Code CLI works in terminal, you can create VS Code tasks:

```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "AI Code Review",
      "type": "shell",
      "command": "claude-code",
      "args": ["Use Claude Sonnet to review the current file"],
      "group": "build"
    }
  ]
}
```

### Shell Aliases

Add convenient aliases to your shell:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias ai-review="claude-code 'Review this code for bugs and improvements'"
alias ai-explain="claude-code 'Explain this code in simple terms'"
alias ai-optimize="claude-code 'Suggest optimizations for this code'"
alias ai-models="claude-code 'List available AI models and their pricing'"
```

---

## Next Steps

With OpenRouter MCP integrated into Claude Code CLI, you can:

1. **Enhance your development workflow** with multiple AI models
2. **Compare model outputs** for the same coding task
3. **Track costs and usage** across different models
4. **Build AI-assisted development routines** tailored to your needs

For more information:
- [Main README](../README.md)
- [API Documentation](API.md)
- [Claude Desktop Integration](CLAUDE_DESKTOP_GUIDE.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [OpenRouter Documentation](https://openrouter.ai/docs)

---

**Last Updated**: 2025-01-12
**Version**: 1.4.0
