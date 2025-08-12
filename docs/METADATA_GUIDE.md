# Model Metadata Enhancement Guide

📊 **Complete guide to the OpenRouter MCP Server's intelligent metadata system**

## Overview

The OpenRouter MCP Server features an advanced metadata enhancement system that automatically analyzes and enriches AI model information with comprehensive details about capabilities, performance characteristics, and usage recommendations. This system makes model discovery, filtering, and selection significantly more efficient and intelligent.

### Key Features

✨ **Automatic Enhancement**: Every model is enriched with metadata when fetched from the API  
🏷️ **Smart Classification**: Intelligent provider detection and category assignment  
🔍 **Advanced Filtering**: Multi-dimensional filtering by provider, capabilities, performance tiers  
📊 **Quality Scoring**: 0-10 quality scores based on context length, pricing, and capabilities  
⚡ **Performance Optimized**: Batch processing with persistent caching for fast access

## Metadata Fields

Each model includes the following enhanced metadata:

### Provider Information
- **Provider**: Canonical provider name (e.g., "openai", "anthropic", "google")
- **Provider Display Name**: Human-readable provider name
- **Provider Website**: Official provider website URL

### Model Categories
Models are automatically categorized based on their capabilities:
- **chat**: Text generation and conversation models
- **image**: Image generation models (text-to-image)
- **audio**: Audio processing models (speech-to-text, text-to-speech)
- **embedding**: Text embedding models for vector representations
- **multimodal**: Models supporting multiple input/output types
- **reasoning**: Advanced reasoning models (e.g., o1 series)
- **code**: Specialized code generation models

### Capabilities
Detailed capability flags for each model:
- **supports_vision**: Can process image inputs
- **supports_function_calling**: Supports function/tool calling
- **supports_streaming**: Supports streaming responses
- **supports_system_prompt**: Accepts system prompts
- **supports_json_mode**: Can output structured JSON
- **supports_tool_use**: Supports tool use (Anthropic-style)
- **max_tokens**: Maximum context window size
- **max_output_tokens**: Maximum output token limit
- **supports_multiple_images**: Can process multiple images
- **supports_pdf**: Can process PDF documents

### Performance & Cost Tiers

#### Performance Tiers
- **premium**: Highest quality models with advanced capabilities
  - Examples: GPT-4, Claude 3 Opus, Gemini Ultra
  - Typical cost: >$0.01 per 1K tokens
- **standard**: Good balance of quality and cost
  - Examples: GPT-3.5 Turbo, Claude 3 Sonnet, Gemini Pro
  - Typical cost: $0.001-$0.01 per 1K tokens
- **economy**: Cost-effective models for simpler tasks
  - Examples: Claude Instant, Llama 2, Mistral 7B
  - Typical cost: <$0.001 per 1K tokens

#### Cost Tiers
- **free**: No cost models
- **low**: Very affordable models
- **medium**: Standard pricing models
- **high**: Premium pricing models

### Version Information
- **version**: Model version identifier
- **release_date**: Model release date (when available)
- **is_latest**: Whether this is the latest version
- **family**: Model family (e.g., "gpt-4", "claude-3")

### Quality Score
A calculated quality score (0-10) based on:
- Context window size
- Output token limits
- Pricing (premium models typically have better quality)
- Provider reputation
- Multimodal capabilities

## Using Metadata for Filtering

### Filter by Provider
```python
# Get all OpenAI models
openai_models = cache.filter_models_by_metadata(provider="openai")

# Get all Anthropic models
anthropic_models = cache.filter_models_by_metadata(provider="anthropic")
```

### Filter by Category
```python
# Get chat models
chat_models = cache.filter_models_by_metadata(category="chat")

# Get image generation models
image_models = cache.filter_models_by_metadata(category="image")

# Get multimodal models
multimodal_models = cache.filter_models_by_metadata(category="multimodal")
```

### Filter by Capabilities
```python
# Get vision-capable models
vision_models = cache.filter_models_by_metadata(
    capabilities={"supports_vision": True}
)

# Get models with large context windows (>100k tokens)
long_context_models = cache.filter_models_by_metadata(
    capabilities={"min_context_length": 100000}
)

# Get models supporting function calling
function_models = cache.filter_models_by_metadata(
    capabilities={"supports_function_calling": True}
)
```

### Filter by Performance/Cost
```python
# Get premium models
premium_models = cache.filter_models_by_metadata(performance_tier="premium")

# Get free models
free_models = cache.filter_models_by_metadata(cost_tier="free")

# Get high-quality models (score >= 8.0)
quality_models = cache.filter_models_by_metadata(min_quality_score=8.0)
```

### Combined Filters
```python
# Get premium OpenAI models with vision support
models = cache.filter_models_by_metadata(
    provider="openai",
    performance_tier="premium",
    capabilities={"supports_vision": True}
)

# Get affordable chat models with long context
models = cache.filter_models_by_metadata(
    category="chat",
    cost_tier="low",
    capabilities={"min_context_length": 50000}
)
```

## Provider Configuration

The system includes comprehensive provider configurations in `src/openrouter_mcp/config/providers.json`:

```json
{
  "providers": {
    "openai": {
      "display_name": "OpenAI",
      "website": "https://openai.com",
      "description": "Creator of GPT models and DALL-E",
      "default_capabilities": {
        "supports_streaming": true,
        "supports_system_prompt": true,
        "supports_function_calling": true,
        "supports_json_mode": true
      },
      "model_families": ["gpt-4", "gpt-3.5", "o1", "dall-e", "whisper"]
    }
  }
}
```

## Metadata in API Responses

When you call `list_available_models`, each model includes full metadata:

```json
{
  "id": "openai/gpt-4-turbo",
  "name": "GPT-4 Turbo",
  "provider": "openai",
  "category": "chat",
  "capabilities": {
    "supports_vision": false,
    "supports_function_calling": true,
    "supports_streaming": true,
    "supports_system_prompt": true,
    "supports_json_mode": true,
    "max_tokens": 128000,
    "max_output_tokens": 4096
  },
  "version_info": {
    "version": "turbo-2024-04-09",
    "release_date": "2024-04-09",
    "is_latest": true,
    "family": "gpt-4"
  },
  "performance_tier": "premium",
  "cost_tier": "high",
  "quality_score": 9.5,
  "tags": ["openai", "chat", "premium", "high", "functions", "long-context", "latest"]
}
```

## Cache Statistics

Get detailed cache statistics including metadata distribution:

```python
stats = cache.get_cache_stats()
# Returns:
{
  "total_models": 250,
  "providers": ["openai", "anthropic", "google", "meta", ...],
  "vision_capable_count": 45,
  "reasoning_model_count": 5,
  "cache_size_mb": 2.5,
  "last_updated": "2025-01-15T10:30:00",
  "is_expired": false,
  "ttl_seconds": 3600
}
```

## Performance Optimization

The metadata system is optimized for performance:

1. **Batch Processing**: All models are enhanced in batch during cache updates
2. **Lazy Evaluation**: Metadata is computed once and cached
3. **Efficient Filtering**: In-memory filtering for fast queries
4. **Smart Caching**: Metadata is persisted with model data

## Extending Metadata

To add custom metadata fields:

1. Update `enhance_model_metadata()` in `src/openrouter_mcp/utils/metadata.py`
2. Add extraction logic for your new field
3. Update filtering methods if needed
4. Add tests for new functionality

## Best Practices

1. **Use Specific Filters**: Combine multiple filters for precise model selection
2. **Check Capabilities**: Always verify model capabilities before use
3. **Consider Cost**: Use performance/cost tiers to optimize spending
4. **Cache Wisely**: Let the cache system handle updates automatically
5. **Monitor Quality**: Use quality scores to select the best models

## Troubleshooting

### Missing Metadata
If a model lacks metadata:
- The system provides sensible defaults
- Provider is set to "unknown"
- Category defaults to "chat"
- Basic capabilities are inferred

### Cache Synchronization
Metadata is automatically synchronized:
- Enhanced when models are fetched from API
- Persisted to cache file
- Loaded on server restart

### Performance Issues
If filtering is slow:
- Check cache size (`get_cache_stats()`)
- Consider increasing cache TTL
- Verify memory usage

## API Reference

### ModelCache Methods

```python
# Get models with metadata
models = await cache.get_models()

# Filter by metadata
filtered = cache.filter_models_by_metadata(
    provider="openai",
    category="chat",
    capabilities={"supports_vision": True},
    performance_tier="premium",
    cost_tier="medium",
    min_quality_score=7.0,
    tags=["latest"]
)

# Get models by tier
tiers = cache.get_models_by_performance_tier()
# Returns: {"premium": [...], "standard": [...], "economy": [...]}

# Get specific model metadata
metadata = cache.get_model_metadata("openai/gpt-4")

# Get cache statistics
stats = cache.get_cache_stats()
```

### Metadata Utilities

```python
from src.openrouter_mcp.utils.metadata import (
    extract_provider_from_id,
    determine_model_category,
    extract_model_capabilities,
    get_model_version_info,
    calculate_quality_score,
    enhance_model_metadata,
    batch_enhance_models
)

# Enhance a single model
enhanced = enhance_model_metadata(raw_model_data)

# Enhance multiple models
enhanced_models = batch_enhance_models(raw_models_list)
```

## Examples

### Finding the Best Model for a Task

```python
# Find the best vision model within budget
vision_models = cache.filter_models_by_metadata(
    category="multimodal",
    capabilities={"supports_vision": True},
    cost_tier="medium",
    min_quality_score=7.0
)

# Sort by quality score
best_vision = sorted(vision_models, key=lambda m: m["quality_score"], reverse=True)[0]
print(f"Best vision model: {best_vision['id']}")
```

### Discovering Latest Models

```python
# Get all latest model versions
latest_models = cache.filter_models_by_metadata(tags=["latest"])

# Get latest models from specific provider
latest_openai = cache.filter_models_by_metadata(
    provider="openai",
    tags=["latest"]
)
```

### Cost-Optimized Selection

```python
# Find cheapest model with specific capabilities
cheap_capable = cache.filter_models_by_metadata(
    capabilities={"min_context_length": 32000},
    cost_tier="low"
)

# Find free models
free_models = cache.filter_models_by_metadata(cost_tier="free")
```

## Conclusion

The enhanced metadata system provides powerful capabilities for model discovery, filtering, and selection. Use it to:
- Find the perfect model for your use case
- Optimize costs while maintaining quality
- Discover new models and capabilities
- Build intelligent model selection logic

For more information, see the main [README](../README.md) or check the [API Documentation](API.md).

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0