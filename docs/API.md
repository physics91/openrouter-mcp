# OpenRouter MCP API Documentation

This document describes the current MCP surface exposed by the OpenRouter MCP server.
The server runs over stdio as an MCP server, not as a standalone HTTP API.

## Overview

- Protocol: Model Context Protocol (MCP)
- Transport: stdio via `openrouter-mcp start`
- Authentication: `OPENROUTER_API_KEY` from environment or secure storage initialized by `openrouter-mcp setup`
- Schema discovery: MCP clients can inspect the live parameter schema through `list_tools()`

## Core Chat Tools

### `chat_with_model`
Generate a chat completion with any OpenRouter model.
Non-streaming responses include runtime thrift metadata; streaming responses attach it to the final chunk only.

### `list_available_models`
List available OpenRouter models with metadata and optional name filtering.

### `get_usage_stats`
Return spending for the authenticated API key using [OpenRouter GET /key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key).
`scope` is `api_key`; `total_cost` is cumulative spending, with current UTC-period
`usage_daily`, `usage_weekly`, and `usage_monthly` counters when provided. Token,
request, and model counts are `null`, because this endpoint does not supply them.
Arbitrary `start_date` / `end_date` ranges are rejected. Historical account activity
requires a separate management-key API and is not fetched by this tool.
Persisted thrift savings remain separately labeled `thrift_scope: "local_runtime"`.
Cross-scope cost-reduction percentages and totals are `null` rather than estimates
combining local savings with key-wide spending.

## Free Model Tools

### `free_chat`
Route a request through free OpenRouter models with automatic fallback and metrics tracking.
Responses include request-scoped runtime thrift metadata.

### `list_free_models`
List currently available free models with quality and availability status.

### `get_free_model_metrics`
Show collected performance metrics and quota information for free-model routing.

## Vision Tools

### `chat_with_vision`
Run multimodal chat with one or more images.
Non-streaming responses include runtime thrift metadata; streaming responses attach it to the final chunk only.

Supported image inputs:
- `type: "base64"`
- `type: "url"`

File path input is not supported.

### `list_vision_models`
List vision-capable models currently exposed by OpenRouter.

## Benchmark Tools

### `benchmark_models`
Run repeated benchmark requests across multiple models and store the result set.
Answer quality is `null` without an answer evaluator. Text length, word overlap,
and coherence heuristics do not measure factual correctness. Default rankings use
measured speed, cost, and throughput; reports preserve unknown quality as `null`
(JSON), an empty cell (CSV), or `Not evaluated` (Markdown).

### `get_benchmark_history`
Read recent saved benchmark runs from the benchmark results directory.

### `compare_model_categories`
Select top models from one or more categories and compare them with a shared prompt.

### `export_benchmark_report`
Export a saved benchmark run to `markdown`, `csv`, or `json`.

### `compare_model_performance`
Apply weighted performance comparison across selected models and return ranking, metrics, and recommendations.
Current default weights are speed 0.3, cost 0.5, throughput 0.2. A nonzero `quality`
weight or category `metric: "quality"` is rejected before billable requests because
no answer evaluator is configured.

## Collective Intelligence Tools

### `collective_chat_completion`
Generate a response by combining multiple models with a consensus strategy.

### `ensemble_reasoning`
Break down a task into sub-problems and synthesize a combined result.

### `adaptive_model_selection`
Choose a best-fit model based on task type, constraints, and performance signals.
Cost-sensitive routes also expose `routing_metrics.thrift_feedback`, which shows the recent runtime-thrift cache-efficiency bucket used to penalize cache deadspots for the selected candidate.
The response also includes `routing_metrics.constraints_applied`, `constraints_unmet`, `filtered_candidates`, `performance_weights`, and `preference_matches` so callers can see which hard guardrails filtered candidates, which normalized weights influenced ranking, and whether `preferred_provider` or `preferred_model_family` matched the winner.
Supported hard-constraint examples include `max_cost`, `excluded_provider`, `required_capabilities`, and `min_context_length`. Soft preference examples include `preferred_provider` and `preferred_model_family`.

### `cross_model_validation`
Validate content with multiple models and aggregate validation signals.
Reviewers must return JSON scores for exactly the requested `validation_criteria`
and structured issues; criterion names may be custom strings and issue descriptions
may be in any language. Missing/malformed scores and provider failures do not count
as successful reviews. At least the configured minimum (default two) distinct
reviewers must succeed. `validation_status` is `complete`, `degraded` (enough reviews
but some failed), or `incomplete` (not enough evidence). Incomplete results return
`INVALID` and zero confidence; they do not establish that the original content is false.
`validator_failures`, `successful_validators`, and per-model `status` expose this
distinction. `validation_score` is the mean of criterion scores, separately from
agreement-weighted `confidence`; these are model assessments, not calibrated accuracy.
`models`, `system_prompt`, `temperature`, and `max_tokens` reach reviewer calls.

### `collaborative_problem_solving`
Run iterative or parallel multi-model collaboration to refine a solution.

## Request Notes

- Raw MCP clients should call `tools/call` with `params.name` and `params.arguments`.
- Chat-style tools accept structured message arrays using MCP-exposed schemas.
- Vision requests must provide image data as base64 or direct URLs.
- Benchmark tools persist result files under the configured benchmark results directory.
- Collective-intelligence tools expose rich request schemas; use your MCP client's live tool schema for exact fields.

## Runtime Thrift Metadata

The following tools expose runtime thrift response metadata:

- `chat_with_model`: request-scoped metadata on non-streaming responses, or on the final streaming chunk
- `chat_with_vision`: request-scoped metadata on non-streaming responses, or on the final streaming chunk
- `free_chat`: request-scoped metadata on the response payload
- `get_usage_stats`: persisted daily rollups grouped by local calendar day, separately scoped from API-key spending

Raw counters are returned under `thrift_metrics`. Common fields include:

- `saved_cost_usd`
- `saved_prompt_tokens`
- `saved_completion_tokens`
- `cached_prompt_tokens`
- `cache_write_prompt_tokens`
- `cache_hit_requests`
- `cache_write_requests`
- `compacted_tokens`
- `coalesced_requests`
- `recent_reuse_requests`
- `deferred_requests`

Human-readable rollups are returned under `thrift_summary`. Important fields include:

- `saved_cost_usd`
- `estimated_cost_without_thrift_usd`
- `effective_cost_reduction_pct`
- `prompt_savings_breakdown`
- `request_savings_breakdown`
- `cache_efficiency`
- `cache_efficiency_by_provider`
- `cache_efficiency_by_model`
- `cache_hotspots` with a per-entry `reason` string that explains why that provider/model ranked near the top
- `cache_deadspots` with a per-entry `reason` string that explains which provider/model is warming cache without enough reuse

Example summary payload:

```json
{
  "thrift_metrics": {
    "saved_cost_usd": 0.01,
    "saved_prompt_tokens": 442,
    "saved_completion_tokens": 20,
    "cached_prompt_tokens": 300,
    "cache_write_prompt_tokens": 100,
    "cache_hit_requests": 1,
    "cache_write_requests": 1,
    "compacted_tokens": 42,
    "coalesced_requests": 1,
    "recent_reuse_requests": 1,
    "deferred_requests": 0
  },
  "thrift_summary": {
    "saved_cost_usd": 0.01,
    "estimated_cost_without_thrift_usd": 0.1,
    "effective_cost_reduction_pct": 10.0,
    "prompt_savings_breakdown": {
      "cache_reuse_tokens": 300,
      "coalesced_prompt_tokens": 100,
      "recent_reuse_prompt_tokens": 25,
      "compacted_tokens": 42
    },
    "request_savings_breakdown": {
      "coalesced_requests": 1,
      "recent_reuse_requests": 1,
      "deferred_requests": 0
    },
    "cache_efficiency": {
      "cached_prompt_tokens": 300,
      "cache_write_prompt_tokens": 100,
      "cache_hit_requests": 1,
      "cache_write_requests": 1,
      "cache_hit_request_rate_pct": 10.0,
      "cache_write_request_rate_pct": 10.0,
      "reuse_to_write_ratio": 3.0
    },
    "cache_efficiency_by_provider": {
      "anthropic": {
        "observed_requests": 4,
        "cached_prompt_tokens": 300,
        "cache_write_prompt_tokens": 100,
        "cache_hit_requests": 1,
        "cache_write_requests": 1,
        "cache_hit_request_rate_pct": 25.0,
        "cache_write_request_rate_pct": 25.0,
        "reuse_to_write_ratio": 3.0,
        "saved_cost_usd": 0.01
      }
    },
    "cache_efficiency_by_model": {
      "anthropic/claude-sonnet-4": {
        "observed_requests": 4,
        "cached_prompt_tokens": 300,
        "cache_write_prompt_tokens": 100,
        "cache_hit_requests": 1,
        "cache_write_requests": 1,
        "cache_hit_request_rate_pct": 25.0,
        "cache_write_request_rate_pct": 25.0,
        "reuse_to_write_ratio": 3.0,
        "saved_cost_usd": 0.01
      }
    },
    "cache_hotspots": {
      "providers": [
        {
          "provider": "anthropic",
          "saved_cost_usd": 0.01,
          "cached_prompt_tokens": 300,
          "cache_hit_request_rate_pct": 25.0,
          "cache_write_request_rate_pct": 25.0,
          "reuse_to_write_ratio": 3.0,
          "reason": "Hit volume keeps pace with writes, so warming converts into real savings"
        }
      ],
      "models": [
        {
          "model": "anthropic/claude-sonnet-4",
          "saved_cost_usd": 0.01,
          "cached_prompt_tokens": 300,
          "cache_hit_request_rate_pct": 25.0,
          "cache_write_request_rate_pct": 25.0,
          "reuse_to_write_ratio": 3.0,
          "reason": "Hit volume keeps pace with writes, so warming converts into real savings"
        }
      ]
    },
    "cache_deadspots": {
      "providers": [],
      "models": []
    }
  }
}
```

`adaptive_model_selection` does not return request-scoped thrift savings. Instead it exposes recent cache-efficiency feedback under `routing_metrics.thrift_feedback` so callers can see whether cost-sensitive routing penalized a provider/model because cache warmups were not converting into real reuse.

Example routing feedback payload:

```json
{
  "routing_metrics": {
    "expected_performance": {
      "response_time": 0.9,
      "quality": 0.84,
      "cost": 0.0021,
      "success_probability": 0.97
    },
    "strategy_used": "adaptive",
    "total_candidates": 4,
    "thrift_feedback": {
      "source": "model",
      "penalty": 0.24,
      "lookback_days": 7,
      "window_start": "2026-04-04",
      "window_end": "2026-04-10",
      "bucket_summary": {
        "observed_requests": 20,
        "cached_prompt_tokens": 24,
        "cache_write_prompt_tokens": 120,
        "cache_hit_requests": 1,
        "cache_write_requests": 8,
        "cache_hit_request_rate_pct": 5.0,
        "cache_write_request_rate_pct": 40.0,
        "reuse_to_write_ratio": 0.2,
        "saved_cost_usd": 0.001
      }
    }
  }
}
```

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

### Usage Stats

```json
{
  "method": "tools/call",
  "params": {
    "name": "get_usage_stats",
    "arguments": {
      "request": {}
    }
  }
}
```

Example MCP Response

```json
{
  "total_cost": 12.34,
  "scope": "api_key",
  "usage_daily": 0.34,
  "usage_weekly": 2.34,
  "usage_monthly": 4.34,
  "total_tokens": null,
  "requests": null,
  "models": null,
  "thrift_scope": "local_runtime",
  "thrift_metrics": {
    "saved_cost_usd": 1.48,
    "saved_prompt_tokens": 657000,
    "saved_completion_tokens": 21000,
    "cached_prompt_tokens": 542000,
    "cache_write_prompt_tokens": 180000,
    "cache_hit_requests": 126,
    "cache_write_requests": 54,
    "compacted_tokens": 24000,
    "coalesced_requests": 18,
    "recent_reuse_requests": 9,
    "deferred_requests": 0
  },
  "thrift_summary": {
    "saved_cost_usd": 1.48,
    "estimated_cost_without_thrift_usd": null,
    "effective_cost_reduction_pct": null,
    "prompt_savings_breakdown": {
      "cache_reuse_tokens": 542000,
      "coalesced_prompt_tokens": 91000,
      "recent_reuse_prompt_tokens": 28000,
      "compacted_tokens": 24000
    },
    "request_savings_breakdown": {
      "coalesced_requests": 18,
      "recent_reuse_requests": 9,
      "deferred_requests": 0
    },
    "cache_efficiency": {
      "cached_prompt_tokens": 542000,
      "cache_write_prompt_tokens": 180000,
      "cache_hit_requests": 126,
      "cache_write_requests": 54,
      "cache_hit_request_rate_pct": null,
      "cache_write_request_rate_pct": null,
      "reuse_to_write_ratio": 3.01
    },
    "cache_efficiency_by_provider": {
      "anthropic": {
        "observed_requests": 203,
        "cached_prompt_tokens": 401000,
        "cache_write_prompt_tokens": 120000,
        "cache_hit_requests": 101,
        "cache_write_requests": 34,
        "cache_hit_request_rate_pct": 49.75,
        "cache_write_request_rate_pct": 16.75,
        "reuse_to_write_ratio": 3.34,
        "saved_cost_usd": 1.02
      }
    },
    "cache_efficiency_by_model": {
      "anthropic/claude-sonnet-4": {
        "observed_requests": 148,
        "cached_prompt_tokens": 355000,
        "cache_write_prompt_tokens": 90000,
        "cache_hit_requests": 88,
        "cache_write_requests": 26,
        "cache_hit_request_rate_pct": 59.46,
        "cache_write_request_rate_pct": 17.57,
        "reuse_to_write_ratio": 3.94,
        "saved_cost_usd": 0.88
      }
    },
    "cache_hotspots": {
      "providers": [
        {
          "provider": "anthropic",
          "saved_cost_usd": 1.02,
          "cached_prompt_tokens": 401000,
          "cache_hit_request_rate_pct": 49.75,
          "cache_write_request_rate_pct": 16.75,
          "reuse_to_write_ratio": 3.34,
          "reason": "Hit volume keeps pace with writes, so warming converts into real savings"
        }
      ],
      "models": [
        {
          "model": "anthropic/claude-sonnet-4",
          "saved_cost_usd": 0.88,
          "cached_prompt_tokens": 355000,
          "cache_hit_request_rate_pct": 59.46,
          "cache_write_request_rate_pct": 17.57,
          "reuse_to_write_ratio": 3.94,
          "reason": "Hit volume keeps pace with writes, so warming converts into real savings"
        }
      ]
    },
    "cache_deadspots": {
      "providers": [
        {
          "provider": "google",
          "saved_cost_usd": 0.03,
          "cached_prompt_tokens": 22000,
          "cache_hit_request_rate_pct": 4.91,
          "cache_write_request_rate_pct": 19.67,
          "reuse_to_write_ratio": 0.41,
          "reason": "Cache writes are visible, but hit conversion is still weak"
        }
      ],
      "models": [
        {
          "model": "google/gemini-2.5-pro",
          "saved_cost_usd": 0.02,
          "cached_prompt_tokens": 15000,
          "cache_hit_request_rate_pct": 3.33,
          "cache_write_request_rate_pct": 18.67,
          "reuse_to_write_ratio": 0.31,
          "reason": "Cache writes are visible, but hit conversion is still weak"
        }
      ]
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
        "speed": 0.3,
        "cost": 0.5,
        "throughput": 0.2
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

### Validation and benchmark boundary behavior

All cross-validator strategies require explicit JSON scores and issues. Empty,
malformed, duplicate-key, or truncated reviews are failed evidence. A consensus
check first generates independent answers, then reviews their agreement with the
candidate; this uses up to two requests per reviewer and the token cap applies to
each request. Agreement measures score differences, not equal issue counts.
Specialized model preferences do not bypass availability or self-review exclusion.

Completion requests reject non-finite/out-of-range temperature, nonpositive token
caps, duplicate model IDs, and invalid model-count ranges. Cross-validation also
rejects empty content and duplicate/blank criteria. Benchmark requests reject
nonpositive run counts, negative/non-finite delays, duplicate IDs, and invalid
ranking weights before initializing API work.

CSV `response_time` is in milliseconds for both basic and enhanced results;
`throughput` is tokens/second. Missing exported measurements are blank in CSV and
null in JSON. Stored quality scores without `quality_evaluation: "provided"` are
legacy, unevaluated data and cannot select a quality winner. The `provided` marker
only identifies a caller-supplied score; it does not certify evaluator accuracy.

Benchmark costs prefer the API's `usage.cost` (including zero). Without it, catalog
prompt/completion USD-per-token rates give an estimate; this estimate does not
include provider-specific cache discounts, dynamic overrides, or other charges.
Missing/invalid fallback pricing produces a failed benchmark instead of ranking
that model as free. See [usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)
and [catalog pricing units](https://openrouter.ai/docs/guides/overview/models#pricing-object).

### Collaborative solving evidence and operational limits

`collaborative_problem_solving` now returns `validation_status` and `is_valid`.
`quality_assessment` and `confidence` are null when the final answer has no completed
review. A review of an earlier draft or one subtask does not validate the assembled
answer. Sequential and hierarchical strategies review the assembled answer. A
fallback consensus answer is unevaluated until that exact answer is reviewed. If
all parallel components fail, the tool returns an error instead of a scored solution.

Consensus and ensemble execution exclude empty/truncated model answers from
successful evidence and honor the caller's model list. Consensus records each API
attempt once, reconciles observed tokens/cost without increasing call counts, and
cancels pending provider requests after an observed quota overage. Cost accounting
is a best-effort local guard: already dispatched provider requests may have incurred
charges before cancellation. It is not a provider-enforced spending cap.

Consensus `quality_metrics` and ensemble `reasoning_quality` are null without an
answer evaluator, with `quality_evaluation: "not_evaluated"`. Their existing
response-derived scalar is available separately as `heuristic_score`; consensus
confidence declares `confidence_basis: "response_heuristic"`. Agreement and fluent
text are not measured correctness. Library-supplied scores are marked `provided`.

Collaborative solving adapts its internal default quorum to an explicit caller
model list without mutating shared configuration; standalone consensus retains its
requested minimum. Ensemble `total_cost` sums observed processing-result costs
(which may themselves be catalog estimates), rather than assignment predictions.
Malformed token counters are rejected before they enter accounting. Both basic and
enhanced benchmark reports preserve measurements when exported and reloaded.

With `decompose: false`, ensemble reasoning assigns the original task once and
returns its response unchanged, with `strategy_used: "none"`. Consensus rejects
an insufficient available model set before generating any answers. Performance
comparisons reject empty or duplicate model lists, and category comparisons require
a positive `top_n`, before starting benchmark work.

Collective cost estimates preserve explicit zero prices and use OpenRouter catalog
prices as USD per token without guessing a different unit from their magnitude.
Reported `usage.cost` still takes precedence over catalog estimates.

Free chat requires explicit zero pricing and text-only output capability. Missing,
negative/dynamic, non-finite, or malformed prices have cost tier `unknown`; any
positive catalog fee prevents free routing. Cached labels are checked again before
selection. Empty text is a failed response; a reported nonzero charge stops retries
instead of recording a successful free response.

Vision requests label PNG, GIF, WebP, and JPEG payloads with their actual MIME type.
Transport success does not establish image understanding: in the 2026-10-06 live
check, GPT-4.1 Nano called a solid red 64×64 PNG blue through both MCP and direct
OpenRouter calls. The same model answered red at 256×256; Gemini 2.5 Flash Lite
answered red at 64×64. This observed provider/model limitation remains outside the
MIME correction and must not be reported as fixed by it.
