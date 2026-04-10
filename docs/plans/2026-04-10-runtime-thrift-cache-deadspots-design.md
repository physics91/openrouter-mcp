# Runtime Thrift Cache Deadspots Design

## Context

`thrift_summary` already highlights cache winners through `cache_hotspots`, but it still hides the opposite side of the problem. Operators can see which provider/model saved money, yet they still have to read the full `cache_efficiency_by_provider` / `cache_efficiency_by_model` blobs to find where cache writes are happening without meaningful reuse.

That is exactly where prompt-cache money gets wasted: repeated cache writes, weak hit conversion, and shallow reuse.

## Decision

Add `cache_deadspots` to `thrift_summary` for both provider and model breakdowns.

Each deadspot entry will be derived from existing bucket metrics only. The ranking will prioritize buckets where cache warming is visible but reuse is weak:

- cache writes exist
- cache hit rate trails cache write rate
- reuse-to-write ratio stays low

The output will mirror `cache_hotspots`:

- `providers`: top 3 worst provider buckets
- `models`: top 3 worst model buckets
- each entry includes a short `reason`

## Why This Approach

### Option 1: Negative savings score

Too fake. We do not actually record negative dollars, so inventing a pseudo-loss number would make the output look more precise than it is.

### Option 2: Heuristic deadspot ranking from current counters

Chosen. It reuses the metrics already collected, keeps the slice small, and gives operators a clear “where is cache warming not paying off?” answer.

### Option 3: Add explicit cache-miss / wasted-token instrumentation

Too large for this step. That would require broader upstream/request instrumentation and a more invasive data model.

## Output Shape

- `cache_deadspots.providers[]`
  - `provider`
  - `saved_cost_usd`
  - `cached_prompt_tokens`
  - `cache_hit_request_rate_pct`
  - `cache_write_request_rate_pct`
  - `reuse_to_write_ratio`
  - `reason`
- `cache_deadspots.models[]`
  - same shape with `model`

## Ranking Rules

- Ignore buckets with no cache writes
- Sort worse buckets first using:
  - lower `reuse_to_write_ratio` first
  - then larger write/hit gap
  - then higher `cache_write_request_rate_pct`
  - then higher `cache_write_prompt_tokens`
- Trim to top 3

## Reason Rules

Reasons stay blunt and operational:

- write-heavy but zero hits
- writes visible but hit conversion weak
- hits exist but reuse depth still poor

## Affected Areas

- `src/openrouter_mcp/runtime_thrift/summary.py`
  - build `cache_deadspots`
- `tests/test_runtime_thrift/test_response_metadata.py`
  - summary shape, sorting, reasons
- `tests/test_handlers/test_chat_handler.py`
  - `get_usage_stats` contract
- docs
  - describe the new summary field and how to read it

## Risks

- Deadspot ranking could accidentally surface tiny, noisy buckets
- Reason strings could overlap too much with hotspot explanations

## Mitigations

- Require cache writes before inclusion
- Prefer write-heavy and reuse-poor buckets in the sort key
- Keep reasons explicitly about underperforming cache warming, not general savings
