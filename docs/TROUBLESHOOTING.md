# Troubleshooting Guide

This guide helps you resolve common issues with the OpenRouter MCP Server.

## Table of Contents
- [Installation Issues](#installation-issues)
- [Configuration Problems](#configuration-problems)
- [Runtime Errors](#runtime-errors)
- [API Issues](#api-issues)
- [Performance Problems](#performance-problems)
- [Integration Issues](#integration-issues)
- [Debug Mode](#debug-mode)
- [Getting Help](#getting-help)

## Installation Issues

### Python Not Found

**Error**: `Python is not installed or not in PATH`

**Solution**:
```bash
# Check Python installation
python --version
# or
python3 --version

# If not installed, download from python.org
# Windows: Add Python to PATH during installation
# macOS: brew install python@3.9
# Linux: sudo apt-get install python3.9
```

### Node.js Version Issues

**Error**: `Node.js version 16+ required`

**Solution**:
```bash
# Check Node.js version
node --version

# Update Node.js
# Windows/macOS: Download from nodejs.org
# Using nvm:
nvm install 16
nvm use 16
```

### Missing Dependencies

**Error**: `ModuleNotFoundError: No module named 'fastmcp'`

**Solution**:
```bash
# Install Python dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt

# If pip is not found
python -m pip install -r requirements.txt
```

### Permission Denied

**Error**: `Permission denied when installing globally`

**Solution**:
```bash
# macOS/Linux: Use sudo
sudo npm install -g openrouter-mcp

# Windows: Run as Administrator
# Or use npx instead of global install
npx openrouter-mcp start
```

## Configuration Problems

### API Key Not Working

**Error**: `Invalid API key` or `Authentication failed`

**Solutions**:

1. **Verify API key**:
```bash
# Re-run initialization
npx openrouter-mcp init

# Check .env file
cat .env | grep OPENROUTER_API_KEY
```

2. **Check API key format**:
```bash
# API key should look like: sk-or-v1-xxxxx
# No quotes or extra spaces in .env file
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
```

3. **Verify API key on OpenRouter**:
- Login to [OpenRouter](https://openrouter.ai)
- Go to API Keys section
- Verify key is active and has credits

### Environment Variables Not Loading

**Error**: `OPENROUTER_API_KEY is not set`

**Solution**:
```bash
# Create .env file in project root
echo "OPENROUTER_API_KEY=your-key-here" > .env

# Verify .env location
ls -la | grep .env

# Manual export (temporary)
export OPENROUTER_API_KEY="your-key-here"
```

### Port Already in Use

**Error**: `Address already in use: 8000`

**Solutions**:

1. **Use different port**:
```bash
npx openrouter-mcp start --port 9000
```

2. **Find and kill process**:
```bash
# macOS/Linux
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## Runtime Errors

### Server Won't Start

**Error**: `Failed to start MCP server`

**Diagnostic Steps**:
```bash
# 1. Check Python path
which python

# 2. Test Python server directly
python -m src.openrouter_mcp.server

# 3. Check for syntax errors
python -m py_compile src/openrouter_mcp/server.py

# 4. Enable debug mode
npx openrouter-mcp start --debug
```

### Memory Issues

**Error**: `MemoryError` or server becomes slow

**Solutions**:

1. **Clear cache**:
```bash
# Delete cache file
rm openrouter_model_cache.json

# Reduce cache size in .env
CACHE_MAX_ITEMS=100
CACHE_TTL_HOURS=0.5
```

2. **Increase memory limit**:
```bash
# Set Node.js memory limit
NODE_OPTIONS="--max-old-space-size=4096" npx openrouter-mcp start
```

### Async Errors

**Error**: `RuntimeError: This event loop is already running`

**Solution**:
```python
# Use nest_asyncio if running in Jupyter
import nest_asyncio
nest_asyncio.apply()

# Or use proper async context
import asyncio
asyncio.run(your_async_function())
```

## API Issues

### Rate Limiting

**Error**: `429 Too Many Requests`

**Solutions**:

1. **Add delays between requests**:
```python
# In benchmark configuration
delay_seconds=2.0  # Increase delay
```

2. **Reduce parallel requests**:
```python
# Reduce concurrent operations
runs_per_model=1  # Instead of 3
```

3. **Check usage limits**:
- Visit OpenRouter dashboard
- Check your rate limits
- Upgrade plan if needed

### Model Not Available

**Error**: `Model not found: model-name`

**Solutions**:

1. **List available models**:
```python
# Use list_available_models tool
models = await list_available_models()
```

2. **Check model ID format**:
```python
# Correct format: provider/model
"openai/gpt-4"  # Correct
"gpt-4"  # Wrong
```

3. **Verify model access**:
- Some models require special access
- Check OpenRouter dashboard for available models

### Image Upload Issues

**Error**: `Image too large` or `Invalid image format`

**Solutions**:

1. **Check image size**:
```python
# Images are automatically resized if > 20MB
# Supported formats: JPEG, PNG, GIF, WebP
```

2. **Verify image path**:
```python
# Use absolute paths
"/home/user/image.jpg"  # Good
"./image.jpg"  # May not work
```

3. **Test with URL**:
```python
# Try with a public image URL first
"https://example.com/test.jpg"
```

## Performance Problems

### Slow Response Times

**Causes and Solutions**:

1. **Network latency**:
```bash
# Test connection to OpenRouter
ping openrouter.ai
curl -w "@curl-format.txt" https://openrouter.ai/api/v1
```

2. **Model selection**:
```python
# Use faster models for testing
"openai/gpt-3.5-turbo"  # Fast
"openai/gpt-4"  # Slower but more capable
```

3. **Caching not working**:
```bash
# Verify cache is enabled
cat .env | grep CACHE

# Check cache file exists
ls -la openrouter_model_cache.json
```

### High Token Usage

**Solutions**:

1. **Set token limits**:
```python
max_tokens=500  # Limit response length
```

2. **Monitor usage**:
```python
# Use get_usage_stats tool
stats = await get_usage_stats(
    start_date="2025-01-01",
    end_date="2025-01-12"
)
```

## Integration Issues

### Claude Desktop Not Detecting Server

**Solutions**:

1. **Verify configuration**:
```bash
# Check config file location
# macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
# Windows: %APPDATA%/Claude/claude_desktop_config.json

# Verify JSON syntax
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python -m json.tool
```

2. **Restart Claude Desktop**:
- Fully quit Claude Desktop (not just close window)
- Restart the application
- Check MCP servers list

3. **Test server independently**:
```bash
# Start server manually
npx openrouter-mcp start --verbose

# Should see: "Server started on localhost:8000"
```

### Claude Code CLI Issues

**Solutions**:

1. **Check configuration**:
```bash
# Verify config file
cat ~/.claude/claude_code_config.json

# Test MCP connection
claude-code "test connection"
```

2. **Update configuration**:
```bash
# Re-run setup
npx openrouter-mcp install-claude-code
```

## Debug Mode

### Enable Detailed Logging

```bash
# Start with debug logging
npx openrouter-mcp start --debug

# Set log level in .env
LOG_LEVEL=debug

# Python debug mode
PYTHONDEBUG=1 npx openrouter-mcp start
```

### Diagnostic Commands

```bash
# Check server status
npx openrouter-mcp status

# Verify Python environment
npx openrouter-mcp check-env

# Test API connection
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models
```

### Log Files

```bash
# View server logs
tail -f server.log

# Search for errors
grep ERROR server.log

# View last 50 lines
tail -n 50 server.log
```

## Common Error Messages

### Error Reference Table

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Connection refused` | Server not running | Start server with `npx openrouter-mcp start` |
| `Invalid JSON` | Malformed request | Check request format and parameters |
| `Timeout error` | Slow network/model | Increase timeout or use faster model |
| `Insufficient credits` | No API credits | Add credits on OpenRouter dashboard |
| `Model not found` | Invalid model ID | Use `list_available_models` to find correct ID |
| `Image decode error` | Corrupted image | Verify image file is valid |
| `Cache error` | Corrupted cache | Delete cache file and restart |

## Getting Help

### Self-Help Resources

1. **Check documentation**:
   - [README](../README.md)
   - [API Documentation](API.md)
   - [FAQ](FAQ.md)

2. **Search existing issues**:
   - GitHub Issues page
   - Search for your error message

3. **Enable debug mode**:
   - Get detailed error information
   - Include in bug reports

### Reporting Issues

When reporting issues, include:

1. **Environment information**:
```bash
npx openrouter-mcp status --diagnostic
```

2. **Error messages**:
   - Complete error output
   - Stack trace if available

3. **Steps to reproduce**:
   - Exact commands used
   - Configuration details

4. **What you've tried**:
   - Solutions attempted
   - Results observed

### Community Support

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share tips
- **Discord**: Join the OpenRouter community

### Professional Support

For enterprise support:
- Contact OpenRouter support
- Priority issue resolution
- Custom integration assistance

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0