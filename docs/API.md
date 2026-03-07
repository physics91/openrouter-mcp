# OpenRouter MCP API Documentation

This document provides detailed API reference for the OpenRouter MCP Server, including all available tools, parameters, and response formats.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Available Tools](#available-tools)
  - [chat_with_model](#chat_with_model)
  - [list_available_models](#list_available_models)
  - [get_usage_stats](#get_usage_stats)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Rate Limits](#rate-limits)
- [Examples](#examples)

## Overview

The OpenRouter MCP Server implements the Model Context Protocol (MCP) to provide access to OpenRouter models through a unified API. All tools are asynchronous and support comprehensive error handling.

**Base URL**: The server runs locally (default: `http://localhost:8000`)
**Protocol**: Model Context Protocol (MCP)
**Framework**: FastMCP

## Authentication

All API requests require an OpenRouter API key. Set your API key in the environment:

```bash
export OPENROUTER_API_KEY="your-api-key-here"
```

Or configure through the CLI:

```bash
npx @physics91/openrouter-mcp@latest init
```

## Available Tools

### chat_with_model

Generate chat completions using any available AI model through OpenRouter.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model identifier (e.g., "openai/gpt-4") |
| `messages` | array | Yes | Array of conversation messages |
| `temperature` | float | No | Sampling temperature (0.0-2.0, default: 0.7) |
| `max_tokens` | integer | No | Maximum tokens to generate |
| `stream` | boolean | No | Enable streaming responses (default: false) |

#### Message Format

```json
{
  "role": "system|user|assistant",
  "content": "message content"
}
```

#### Response Format

**Non-streaming response:**
```json
{
  "id": "cmpl-xxx",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "openai/gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 10,
    "total_tokens": 30
  }
}
```

**Streaming response:**
```json
[
  {
    "id": "cmpl-xxx",
    "object": "chat.completion.chunk",
    "created": 1677652288,
    "model": "openai/gpt-4",
    "choices": [
      {
        "index": 0,
        "delta": {
          "role": "assistant",
          "content": "Hello"
        },
        "finish_reason": null
      }
    ]
  },
  {
    "id": "cmpl-xxx",
    "object": "chat.completion.chunk",
    "created": 1677652289,
    "model": "openai/gpt-4",
    "choices": [
      {
        "index": 0,
        "delta": {
          "content": "! How can I help you today?"
        },
        "finish_reason": "stop"
      }
    ]
  }
]
```

#### Example Request

```json
{
  "model": "openai/gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant that explains complex topics simply."
    },
    {
      "role": "user",
      "content": "Explain quantum computing in simple terms."
    }
  ],
  "temperature": 0.7,
  "max_tokens": 500
}
```

#### Supported Models

Popular models include:

**OpenAI Models:**
- `openai/gpt-4` - Most capable GPT-4 model
- `openai/gpt-4-turbo` - Latest GPT-4 with improved speed
- `openai/gpt-3.5-turbo` - Fast and cost-effective

**Anthropic Models:**
- `anthropic/claude-3-opus` - Most capable Claude model
- `anthropic/claude-3-sonnet` - Balanced capability and speed
- `anthropic/claude-3-haiku` - Fast and efficient

**Open Source Models:**
- `meta-llama/llama-2-70b-chat` - Meta's flagship model
- `mistralai/mixtral-8x7b-instruct` - Efficient mixture of experts
- `microsoft/wizardlm-2-8x22b` - High-quality instruction following

Use `list_available_models` to get the complete list.

---

### list_available_models

Retrieve information about all available models from OpenRouter.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filter_by` | string | No | Filter models by name substring |

#### Response Format

```json
[
  {
    "id": "openai/gpt-4",
    "name": "GPT-4",
    "description": "More capable than any GPT-3.5 model, able to do more complex tasks, and optimized for chat.",
    "pricing": {
      "prompt": "0.00003",
      "completion": "0.00006"
    },
    "context_length": 8192,
    "architecture": {
      "modality": "text",
      "tokenizer": "cl100k_base",
      "instruct_type": "chatml"
    },
    "top_provider": {
      "max_completion_tokens": 4096,
      "is_moderated": true
    },
    "per_request_limits": {
      "prompt_tokens": "40960000",
      "completion_tokens": "40960000"
    }
  }
]
```

#### Model Information Fields

| Field | Description |
|-------|-------------|
| `id` | Unique model identifier for API calls |
| `name` | Human-readable model name |
| `description` | Model capabilities and use cases |
| `pricing.prompt` | Cost per prompt token (USD) |
| `pricing.completion` | Cost per completion token (USD) |
| `context_length` | Maximum context window size |
| `architecture.modality` | Input types supported (text, vision, etc.) |
| `top_provider.max_completion_tokens` | Maximum response length |

#### Example Request

```json
{
  "filter_by": "gpt"
}
```

#### Example Response

```json
[
  {
    "id": "openai/gpt-4",
    "name": "GPT-4",
    "description": "More capable than any GPT-3.5 model...",
    "pricing": {
      "prompt": "0.00003",
      "completion": "0.00006"
    },
    "context_length": 8192
  },
  {
    "id": "openai/gpt-3.5-turbo",
    "name": "GPT-3.5 Turbo",
    "description": "Fast, inexpensive model for simple tasks...",
    "pricing": {
      "prompt": "0.0000015",
      "completion": "0.000002"
    },
    "context_length": 4096
  }
]
```

---

### get_usage_stats

Retrieve API usage statistics and costs for your OpenRouter account.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | No | Start date for stats (YYYY-MM-DD format) |
| `end_date` | string | No | End date for stats (YYYY-MM-DD format) |

#### Response Format

```json
{
  "data": [
    {
      "date": "2024-01-15",
      "total_cost": 12.45,
      "total_tokens": 150000,
      "requests": 250,
      "models": [
        {
          "model": "openai/gpt-4",
          "requests": 100,
          "cost": 8.20,
          "tokens": 80000
        },
        {
          "model": "anthropic/claude-3-sonnet",
          "requests": 150,
          "cost": 4.25,
          "tokens": 70000
        }
      ]
    }
  ],
  "summary": {
    "total_cost": 12.45,
    "total_tokens": 150000,
    "total_requests": 250,
    "date_range": {
      "start": "2024-01-15",
      "end": "2024-01-15"
    }
  }
}
```

#### Usage Information Fields

| Field | Description |
|-------|-------------|
| `date` | Date for the usage data |
| `total_cost` | Total cost in USD for the period |
| `total_tokens` | Total tokens used (prompt + completion) |
| `requests` | Total number of API requests |
| `models` | Breakdown by individual models |
| `summary` | Aggregated statistics for the entire period |

#### Example Request

```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

## Data Models

### ChatMessage

```json
{
  "role": "system|user|assistant",
  "content": "string"
}
```

### ChatCompletionRequest

```json
{
  "model": "string",
  "messages": [ChatMessage],
  "temperature": "float (0.0-2.0)",
  "max_tokens": "integer|null",
  "stream": "boolean"
}
```

### ModelListRequest

```json
{
  "filter_by": "string|null"
}
```

### UsageStatsRequest

```json
{
  "start_date": "string|null (YYYY-MM-DD)",
  "end_date": "string|null (YYYY-MM-DD)"
}
```

## Error Handling

All tools implement comprehensive error handling. Common error types:

### Authentication Errors

```json
{
  "error": {
    "type": "authentication_error",
    "message": "Invalid API key provided",
    "code": 401
  }
}
```

### Rate Limit Errors

```json
{
  "error": {
    "type": "rate_limit_error",
    "message": "Rate limit exceeded. Please try again later.",
    "code": 429,
    "retry_after": 60
  }
}
```

### Model Not Found

```json
{
  "error": {
    "type": "model_not_found_error",
    "message": "The requested model 'invalid/model' was not found",
    "code": 404
  }
}
```

### Validation Errors

```json
{
  "error": {
    "type": "validation_error",
    "message": "Temperature must be between 0.0 and 2.0",
    "code": 400,
    "details": {
      "field": "temperature",
      "value": 3.0
    }
  }
}
```

### Server Errors

```json
{
  "error": {
    "type": "server_error",
    "message": "Internal server error occurred",
    "code": 500
  }
}
```

## Rate Limits

OpenRouter implements rate limiting based on your plan:

- **Free Tier**: 10 requests/minute
- **Paid Plans**: Varies by plan (up to 1000 requests/minute)

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1677652400
```

When rate limited, implement exponential backoff:

```python
import time
import random

def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise

            # Exponential backoff with jitter
            delay = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
```

## Examples

### Complete Chat Conversation

```json
{
  "tool": "chat_with_model",
  "parameters": {
    "model": "anthropic/claude-3-sonnet",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful coding assistant. Provide clear, concise answers."
      },
      {
        "role": "user",
        "content": "How do I implement a binary search in Python?"
      }
    ],
    "temperature": 0.3,
    "max_tokens": 1000
  }
}
```

### Model Comparison

```json
{
  "tool": "list_available_models",
  "parameters": {
    "filter_by": "claude"
  }
}
```

Response will include all Claude models with pricing comparison.

### Cost Tracking

```json
{
  "tool": "get_usage_stats",
  "parameters": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }
}
```

### Streaming Chat

```json
{
  "tool": "chat_with_model",
  "parameters": {
    "model": "openai/gpt-4",
    "messages": [
      {
        "role": "user",
        "content": "Write a short story about a robot learning to paint."
      }
    ],
    "stream": true,
    "temperature": 0.8
  }
}
```

## Best Practices

### Model Selection

1. **For reasoning tasks**: Use `openai/gpt-4` or `anthropic/claude-3-opus`
2. **For speed**: Use `openai/gpt-3.5-turbo` or `anthropic/claude-3-haiku`
3. **For coding**: Use `anthropic/claude-3-sonnet` or `openai/gpt-4`
4. **For cost optimization**: Use `mistralai/mixtral-8x7b-instruct`

### Parameter Tuning

- **Temperature 0.0-0.3**: Factual, deterministic responses
- **Temperature 0.4-0.7**: Balanced creativity and accuracy
- **Temperature 0.8-1.0**: Creative, varied responses
- **Temperature 1.1-2.0**: Highly creative, potentially inconsistent

### Error Handling

Always implement proper error handling:

```python
try:
    response = await chat_with_model(request)
except AuthenticationError:
    # Handle invalid API key
    pass
except RateLimitError:
    # Implement backoff strategy
    pass
except ModelNotFoundError:
    # Fallback to alternative model
    pass
except Exception as e:
    # Log error and handle gracefully
    logger.error(f"Unexpected error: {e}")
```

### Cost Optimization

1. Use `get_usage_stats` to monitor costs
2. Choose appropriate models for each task
3. Set reasonable `max_tokens` limits
4. Implement caching for repeated queries
5. Use streaming for long responses to improve UX

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Set up the OpenRouter MCP Server
- [Benchmarking Guide](BENCHMARK_GUIDE.md) - Compare model performance
- [Model Metadata Guide](METADATA_GUIDE.md) - Model filtering and categorization
- [Multimodal Guide](MULTIMODAL_GUIDE.md) - Image and vision capabilities
- [Troubleshooting](TROUBLESHOOTING.md) - API usage issues and solutions

For project overview and the main documentation entrypoint, see the [README](../README.md).

---

**Last Updated**: 2025-01-12
**Version**: 1.4.0

For more information, see the [main README](../README.md) or visit [OpenRouter Documentation](https://openrouter.ai/docs).
