# Frequently Asked Questions (FAQ)

Quick answers to common questions about the OpenRouter MCP Server.

## Table of Contents
- [General Questions](#general-questions)
- [Setup & Installation](#setup--installation)
- [Usage Questions](#usage-questions)
- [Model Questions](#model-questions)
- [Pricing & Costs](#pricing--costs)
- [Technical Questions](#technical-questions)
- [Troubleshooting](#troubleshooting)

## General Questions

### What is OpenRouter MCP Server?
The OpenRouter MCP Server is a Model Context Protocol (MCP) implementation that provides unified access to 200+ AI models through OpenRouter's API. It allows you to use models from OpenAI, Anthropic, Google, Meta, and many others through a single interface.

### What is MCP (Model Context Protocol)?
MCP is a standard protocol developed by Anthropic that enables AI assistants to connect with external tools and services. It provides a structured way for AI models to interact with APIs, databases, and other resources.

### Why use OpenRouter instead of direct API access?
- **Single API key**: Access all models with one API key
- **Unified interface**: Same API format for all models
- **Cost optimization**: Compare prices across providers
- **Fallback options**: Automatically switch models if one fails
- **No vendor lock-in**: Easy to switch between models

### What models are supported?
Over 200 models including:
- OpenAI (GPT-4, GPT-3.5, DALL-E)
- Anthropic (Claude 3 Opus, Sonnet, Haiku)
- Google (Gemini Pro, Gemini Vision)
- Meta (Llama 3, Llama Vision)
- And many more open-source models

## Setup & Installation

### What are the system requirements?
- **Node.js**: Version 16 or higher
- **Python**: Version 3.9 or higher
- **Memory**: At least 2GB RAM recommended
- **Storage**: 500MB for installation
- **OS**: Windows, macOS, or Linux

### Do I need to install Python separately?
Yes, Python 3.9+ must be installed on your system. The Node.js package manages the Python server but doesn't include Python itself.

### How do I get an OpenRouter API key?
1. Visit [OpenRouter.ai](https://openrouter.ai)
2. Sign up for a free account
3. Navigate to API Keys section
4. Create a new API key
5. Add credits to your account

### Can I use this without Claude Desktop?
Yes! The MCP server can be used:
- With Claude Desktop app
- With Claude Code CLI
- As a standalone Python package
- Through direct API calls

### How do I update to the latest version?
```bash
# If installed globally
npm update -g openrouter-mcp

# If using npx
npm cache clean --force
npx openrouter-mcp@latest start
```

## Usage Questions

### How do I switch between models?
Simply change the model parameter in your request:
```json
{
  "model": "openai/gpt-4",  // Change this
  "messages": [...]
}
```

### Can I use multiple models in one session?
Yes! You can call different models in sequence or even run benchmarks to compare them:
```python
# Compare models
results = await benchmark_models(
    models=["openai/gpt-4", "anthropic/claude-3"],
    prompt="Your prompt here"
)
```

### How do I send images to vision models?
Use the `chat_with_vision` tool:
```json
{
  "model": "openai/gpt-4o",
  "messages": [{"role": "user", "content": "What's in this image?"}],
  "images": [{"data": "/path/to/image.jpg", "type": "path"}]
}
```

### What image formats are supported?
- **Formats**: JPEG, PNG, GIF, WebP
- **Sources**: File paths, URLs, base64 strings
- **Size**: Automatically resized if >20MB

### How do I enable streaming responses?
Add the `stream` parameter:
```json
{
  "model": "openai/gpt-4",
  "messages": [...],
  "stream": true
}
```

## Model Questions

### Which model should I use?
It depends on your needs:
- **Fast responses**: `openai/gpt-3.5-turbo`, `anthropic/claude-3-haiku`
- **Best quality**: `openai/gpt-4`, `anthropic/claude-3-opus`
- **Vision tasks**: `openai/gpt-4o`, `anthropic/claude-3-opus`
- **Code generation**: `anthropic/claude-3-sonnet`, `openai/gpt-4`
- **Budget-friendly**: `meta-llama/llama-3.1-8b`, `mistralai/mistral-7b`

### How do I find available models?
Use the `list_available_models` tool:
```python
# List all models
models = await list_available_models()

# Filter by provider
models = await list_available_models(provider="openai")

# Filter by capability
vision_models = await list_vision_models()
```

### What's the difference between model versions?
- **Base models**: Original training (`gpt-4`)
- **Turbo models**: Optimized for speed (`gpt-4-turbo`)
- **Preview models**: Latest features (`gpt-4-preview`)
- **Instruct models**: Fine-tuned for instructions (`llama-instruct`)

### Can I use custom/fine-tuned models?
Yes, if they're available on OpenRouter. Check the model list or OpenRouter dashboard for custom models.

## Pricing & Costs

### How much does it cost?
Costs vary by model. Examples (per 1M tokens):
- GPT-3.5 Turbo: ~$0.50-2.00
- GPT-4: ~$10-30
- Claude 3 Haiku: ~$0.25-1.25
- Llama models: Often free or very low cost

Use `list_available_models()` to see current prices.

### How can I track my usage?
Use the `get_usage_stats` tool:
```python
stats = await get_usage_stats(
    start_date="2025-01-01",
    end_date="2025-01-12"
)
```

### How can I reduce costs?
1. **Use efficient models**: Choose faster/smaller models when possible
2. **Set token limits**: Use `max_tokens` parameter
3. **Enable caching**: Reduces repeated API calls
4. **Batch requests**: Process multiple items together
5. **Monitor usage**: Track spending with usage stats

### Is there a free tier?
OpenRouter offers free credits for new users. Some open-source models may have free or very low-cost tiers.

## Technical Questions

### How does caching work?
The server uses a two-layer cache:
1. **Memory cache**: Fast, in-memory LRU cache
2. **File cache**: Persistent JSON cache

Cache TTL and size can be configured in `.env`.

### Can I disable caching?
Yes, set in `.env`:
```env
CACHE_TTL_HOURS=0
```

### What's the maximum request size?
- **Text**: Generally 100k-200k tokens depending on model
- **Images**: 20MB (automatically resized if larger)
- **Batch requests**: Depends on model context window

### How do I handle rate limits?
The server automatically:
- Retries with exponential backoff
- Respects rate limit headers
- Queues requests when needed

You can also add delays in benchmarks:
```python
delay_seconds=2.0  # Wait between requests
```

### Is my data secure?
- API keys are stored locally in `.env`
- All API calls use HTTPS
- No data is stored by the MCP server (except cache)
- OpenRouter's privacy policy applies to API usage

### Can I run this in production?
Yes, but consider:
- Use environment variables for configuration
- Implement proper error handling
- Set up monitoring and logging
- Use a process manager (PM2, systemd)
- Consider rate limits and costs

## Troubleshooting

### Server won't start?
1. Check Python and Node.js versions
2. Verify API key is set
3. Try a different port
4. Check the [Troubleshooting Guide](TROUBLESHOOTING.md)

### Getting authentication errors?
1. Verify API key is correct
2. Check you have credits on OpenRouter
3. Ensure no extra spaces in `.env` file

### Models not showing up?
1. Refresh model cache: Delete `openrouter_model_cache.json`
2. Check internet connection
3. Verify API key has access to models

### Slow performance?
1. Use faster models (turbo variants)
2. Reduce token limits
3. Enable caching
4. Check network latency

### Need more help?
- Read the [Troubleshooting Guide](TROUBLESHOOTING.md)
- Check [GitHub Issues](https://github.com/your-repo/issues)
- Join the community Discord
- Contact OpenRouter support

## Advanced Questions

### Can I modify the server code?
Yes! The project is open source. See [Contributing Guide](../CONTRIBUTING.md) for development setup.

### How do I add a new feature?
1. Fork the repository
2. Create a feature branch
3. Implement with tests (TDD)
4. Submit a pull request

### Can I use this with other MCP clients?
Yes, the server follows MCP standards and should work with any MCP-compatible client.

### How do I run tests?
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# With coverage
pytest --cov=src/openrouter_mcp
```

### Can I deploy this as a web service?
Yes, you can wrap it in a web framework like FastAPI or Flask. See the [Architecture Guide](ARCHITECTURE.md) for details.

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0

**Still have questions?** Open an issue on GitHub or check our other documentation!