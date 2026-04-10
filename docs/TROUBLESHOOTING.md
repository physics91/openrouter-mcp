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
# macOS: brew install python@3.11
# Linux: sudo apt-get install python3.11
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
sudo npm install -g @physics91/openrouter-mcp

# Windows: Run as Administrator
# Or use npx instead of global install
npx @physics91/openrouter-mcp@latest start
```

## Configuration Problems

### API Key Not Working

**Error**: `Invalid API key` or `Authentication failed`

**Solutions**:

1. **Verify API key**:
```bash
# Re-run initialization
npx @physics91/openrouter-mcp@latest init

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
npx @physics91/openrouter-mcp@latest start --port 9000
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
npx @physics91/openrouter-mcp@latest start --debug
```

### Memory Issues

**Error**: `MemoryError` or server becomes slow

**Solutions**:

1. **Clear cache**:
```bash
# Delete cache file
rm .cache/openrouter_model_cache.json
```

# Reduce cache size in code (ModelCache settings)
```python
from openrouter_mcp.models.cache import ModelCache

cache = ModelCache(ttl_hours=0.5, max_memory_items=100)
print(cache.get_cache_stats())
```

2. **Increase memory limit**:
```bash
# Set Node.js memory limit
NODE_OPTIONS="--max-old-space-size=4096" npx @physics91/openrouter-mcp@latest start
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
ls -la .cache/openrouter_model_cache.json
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

3. **Interpret runtime thrift metadata**:
```python
stats["thrift_summary"]
stats["thrift_metrics"]
```

`get_usage_stats(start_date=..., end_date=...)` now reads thrift savings from persisted daily rollups, filtered by the same local calendar day window. So if the thrift numbers look off, check the date range first before blaming the provider.

Use these fields to tell which cost-saving layer is working and which one is asleep at the wheel:

- `saved_cost_usd`: Estimated dollars avoided by runtime thrift
- `effective_cost_reduction_pct`: Effective reduction versus estimated cost without thrift
- `prompt_savings_breakdown`: Prompt-token savings from cache reuse, in-flight coalescing, short-lived recent reuse, and compaction
- `request_savings_breakdown`: Request-count savings split between in-flight coalescing, recent reuse, and deferred batch export
- `cache_efficiency`: Cache writes versus cache re-use volume, plus request hit/write rates
- `cache_efficiency_by_provider`: Which providers actually convert cache writes into hits on real upstream traffic
- `cache_efficiency_by_model`: The same breakdown at exact model granularity when one provider has mixed winners and losers
- `cache_hotspots`: Human-friendly top providers/models so you do not need to eyeball the full breakdown blob like a caveman
- `cache_hotspots[*].reason`: One-line explanation for why that provider/model is ranking near the top right now
- `cache_deadspots`: Human-friendly top providers/models where cache warmups are not converting into enough hits
- `cache_deadspots[*].reason`: One-line explanation for why that provider/model is underperforming right now

**What the numbers usually mean**:

- `saved_cost_usd` stays near `0.0` while spend is rising:
  runtime thrift is not hitting enough. Check repeated prompts, prefix cache eligibility, and whether identical requests are actually identical.
- `effective_cost_reduction_pct` is low:
  request mix is too unique, prompt prefixes are unstable, or compaction is not triggering before long histories blow up.
- `prompt_savings_breakdown.cache_reuse_tokens` is low:
  prefix caching is not landing. Look for changing system prompts, volatile tool definitions, or short prompts that never cross provider cache thresholds.
- `prompt_savings_breakdown.coalesced_prompt_tokens` is low during bursts:
  traffic may be semantically similar but not exact-match identical, so the coalescer has nothing to collapse.
- `prompt_savings_breakdown.recent_reuse_prompt_tokens` is low even when identical requests arrive back-to-back:
  your TTL grace window is probably too short, disabled, or the requests differ just enough to miss exact-match reuse.
- `request_savings_breakdown.recent_reuse_requests` stays at `0` while tail-burst traffic is obvious:
  TTL-based reuse is disabled, too short-lived, or callers are mutating request payloads between retries.
- `prompt_savings_breakdown.compacted_tokens` is `0` on long conversations:
  context compaction is disabled, thresholds are too high, or the model context window is large enough that compaction never triggers.
- `cache_efficiency.cache_hit_request_rate_pct` is near `0.0` even though traffic repeats:
  cacheable requests are not stable enough, provider cache thresholds are not crossed, or your prefix planner is disabled.
- `cache_efficiency.cache_write_request_rate_pct` is high but `cache_hit_request_rate_pct` stays low:
  you are warming cache on a lot of requests but almost never getting a second hit. That is just write overhead in a fake mustache.
- `cache_efficiency_by_provider.anthropic.cache_hit_request_rate_pct` is healthy but another provider stays near `0.0`:
  one provider/model family has stable prefixes and the other is just churning unique prompts. Stop treating them like the same traffic class.
- `cache_hotspots.providers[0]` keeps showing the same winner:
  good. That means one traffic class is clearly carrying savings and you can optimize the losers separately instead of pretending everything behaves the same.
- `cache_hotspots.providers[0].reason` keeps talking about writes not converting into hits:
  you have a warming problem, not a scaling victory. Stabilize prefixes or stop trying to cache one-shot traffic.
- `cache_deadspots.providers[0]` keeps showing the same provider:
  that traffic class is paying cache warmup cost without enough repeat traffic. Either stabilize prefixes or stop forcing cache there.
- `cache_deadspots.providers[0].reason` says warmups are being wasted:
  zero-hit or near-zero-hit cache writes are piling up. That is not optimization, that is cosplay.
- `cache_efficiency.reuse_to_write_ratio` stays below `1.0`:
  you are paying cache write cost without enough re-use. Stabilize prompt prefixes or stop trying to cache one-off traffic.

If these values look wrong, compare them against runtime thrift policy flags and the actual request mix before blaming the provider. Half the time the bug is just "every prompt is unique" dressed up as observability.

### Adaptive Router Keeps Picking Cache Deadspots

`adaptive_model_selection` now exposes `routing_metrics.thrift_feedback` for the selected candidate on cost-sensitive routes. That blob is not request savings; it is the recent deadspot signal the adaptive router used while scoring the winner.

Use these fields to tell whether the router is penalizing the right thing:

- `routing_metrics.thrift_feedback.source`: `model` means exact model bucket was used, `provider` means the router had to fall back to a provider-level bucket, `none` means there was no recent thrift data at all
- `routing_metrics.thrift_feedback.penalty`: bounded penalty applied to cost-sensitive scoring. `0.0` means the selected candidate was not treated as a deadspot
- `routing_metrics.thrift_feedback.lookback_days`: local-day window size used for the feedback snapshot
- `routing_metrics.thrift_feedback.window_start` / `window_end`: the exact local calendar day range read from persisted thrift rollups
- `routing_metrics.thrift_feedback.bucket_summary`: normalized counters behind the penalty, including `cache_hit_requests`, `cache_write_requests`, `cache_hit_request_rate_pct`, and `reuse_to_write_ratio`
- `routing_metrics.constraints_applied`: normalized hard-filter and soft-preference keys the router actually honored, including `max_cost`, `min_context_length`, `preferred_provider`, and `preferred_model_family`
- `routing_metrics.constraints_unmet`: constraint classes that filtered candidates out before ranking
- `routing_metrics.filtered_candidates`: how many candidates got dropped by hard guardrails
- `routing_metrics.performance_weights`: normalized `accuracy` / `speed` / `cost` weights derived from `performance_requirements`
- `routing_metrics.preference_matches`: which soft preferences actually matched the selected model

**What the numbers usually mean**:

- `source` is `none`:
  the router had no recent thrift rollup for that model/provider, so selection happened without cache deadspot input. Check whether rollups exist for the date window before whining about routing.
- `source` is `provider`:
  exact model-level history was missing, so the router used broader provider history. Good enough for guardrails, but less precise than model-level buckets.
- `penalty` is high and `bucket_summary.cache_hit_requests` stays near `0`:
  that lane keeps warming cache without any real follow-up hits. The router is right to distrust it for cost-sensitive work.
- `bucket_summary.cache_write_request_rate_pct` is much higher than `cache_hit_request_rate_pct`:
  you are paying write overhead but not getting reuse back. Stabilize prefixes or stop pretending that traffic is cacheable.
- `reuse_to_write_ratio` stays below `1.0`:
  cache writes are not earning themselves back yet. If this persists, that provider/model belongs in the loser bucket until traffic shape changes.

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
npx @physics91/openrouter-mcp@latest start --verbose

# Should see: "Server started on localhost:8000"
```

### Claude Code CLI Issues

**Solutions**:

1. **Check configuration**:
```bash
# List configured MCP servers
claude mcp list

# Inspect the OpenRouter entry
claude mcp get openrouter

# If using project scope, inspect .mcp.json
cat .mcp.json | python -m json.tool
```

2. **Update configuration**:
```bash
# Re-register in Claude Code user scope
claude mcp add --transport stdio --scope user openrouter -- npx @physics91/openrouter-mcp start
```

## Debug Mode

### Enable Detailed Logging

```bash
# Start with debug logging
npx @physics91/openrouter-mcp@latest start --debug

# Set log level in .env
LOG_LEVEL=debug

# Python debug mode
PYTHONDEBUG=1 npx @physics91/openrouter-mcp@latest start
```

### Diagnostic Commands

```bash
# Check server status
npx @physics91/openrouter-mcp@latest status

# Verify Python environment
python --version
python -c "import fastmcp, httpx, pydantic; print('Python dependencies OK')"

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
| `Connection refused` | Server not running | Start server with `npx @physics91/openrouter-mcp@latest start` |
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
npx @physics91/openrouter-mcp@latest status
node --version
python --version
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
**Version**: 1.4.0
