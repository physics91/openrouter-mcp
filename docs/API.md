# OpenRouter MCP API Documentation

This document describes the current MCP surface exposed by the OpenRouter MCP server.
The server runs over stdio as an MCP server, not as a standalone HTTP API.

## Overview

- Protocol: Model Context Protocol (MCP)
- Transport: stdio via `openrouter-mcp start`
- Authentication: `OPENROUTER_API_KEY` from environment or secure storage initialized by `openrouter-mcp init`
- Schema discovery: MCP clients can inspect the live parameter schema through `list_tools()`

## Core Chat Tools

### `chat_with_model`
Generate a chat completion with any OpenRouter model.

### `list_available_models`
List available OpenRouter models with metadata and optional name filtering.

### `get_usage_stats`
Return usage and cost information for the configured OpenRouter account.

## Free Model Tools

### `free_chat`
Route a request through free OpenRouter models with automatic fallback and metrics tracking.

### `list_free_models`
List currently available free models with quality and availability status.

### `get_free_model_metrics`
Show collected performance metrics and quota information for free-model routing.

## Vision Tools

### `chat_with_vision`
Run multimodal chat with one or more images.

Supported image inputs:
- `type: "base64"`
- `type: "url"`

File path input is not supported.

### `list_vision_models`
List vision-capable models currently exposed by OpenRouter.

## Benchmark Tools

### `benchmark_models`
Run repeated benchmark requests across multiple models and store the result set.

### `get_benchmark_history`
Read recent saved benchmark runs from the benchmark results directory.

### `compare_model_categories`
Select top models from one or more categories and compare them with a shared prompt.

### `export_benchmark_report`
Export a saved benchmark run to `markdown`, `csv`, or `json`.

### `compare_model_performance`
Apply weighted performance comparison across selected models and return ranking, metrics, and recommendations.

## Collective Intelligence Tools

### `collective_chat_completion`
Generate a response by combining multiple models with a consensus strategy.

### `ensemble_reasoning`
Break down a task into sub-problems and synthesize a combined result.

### `adaptive_model_selection`
Choose a best-fit model based on task type, constraints, and performance signals.

### `cross_model_validation`
Validate content with multiple models and aggregate validation signals.

### `collaborative_problem_solving`
Run iterative or parallel multi-model collaboration to refine a solution.

## Request Notes

- Raw MCP clients should call `tools/call` with `params.name` and `params.arguments`.
- Chat-style tools accept structured message arrays using MCP-exposed schemas.
- Vision requests must provide image data as base64 or direct URLs.
- Benchmark tools persist result files under the configured benchmark results directory.
- Collective-intelligence tools expose rich request schemas; use your MCP client's live tool schema for exact fields.

## Example MCP Requests

### Chat

```json
{
  "method": "tools/call",
  "params": {
    "name": "chat_with_model",
    "arguments": {
      "request": {
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [
          {"role": "user", "content": "Summarize this project in one paragraph."}
        ],
        "temperature": 0.3
      }
    }
  }
}
```

### Vision

```json
{
  "method": "tools/call",
  "params": {
    "name": "chat_with_vision",
    "arguments": {
      "request": {
        "model": "openai/gpt-4o",
        "messages": [
          {"role": "user", "content": "Describe the chart in this image."}
        ],
        "images": [
          {
            "data": "https://example.com/chart.png",
            "type": "url"
          }
        ]
      }
    }
  }
}
```

### Benchmark

```json
{
  "method": "tools/call",
  "params": {
    "name": "compare_model_performance",
    "arguments": {
      "models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
      "weights": {
        "speed": 0.2,
        "cost": 0.3,
        "quality": 0.4,
        "throughput": 0.1
      }
    }
  }
}
```

## Related Documents

- `README.md`
- `docs/MULTIMODAL_GUIDE.md`
- `docs/BENCHMARK_GUIDE.md`
- `docs/COLLECTIVE_INTELLIGENCE_INTEGRATION.md`
- `docs/SECURE_STORAGE_INTEGRATION.md`
