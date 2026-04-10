# Adaptive Router Thrift Feedback Design

## Context

`AdaptiveRouter` already scores models using predicted quality, latency, cost, and load. But its cost-aware paths are still blind to runtime thrift reality.

That means `COST_OPTIMIZED` and cost-leaning `ADAPTIVE` routing can keep preferring a provider/model that looks cheap on paper while prompt-cache warming is getting wasted in practice. The system already records that signal under runtime thrift metrics, including provider/model cache deadspots, but the router never consumes it.

## Decision

Add a soft runtime-thrift penalty to `AdaptiveRouter` for cost-sensitive strategies only:

- `RoutingStrategy.COST_OPTIMIZED`
- `RoutingStrategy.ADAPTIVE` when the optimization objective is:
  - `MINIMIZE_COST`
  - `BALANCE_ALL`

The router will read recent runtime thrift metrics once per routing decision, derive a machine-facing penalty from raw provider/model cache-efficiency buckets, and reduce model scores when cache writes are not converting into enough hits.

This is a penalty, not a hard block.

## Why This Approach

### Option 1: Hard-block deadspot models

Too aggressive. A short-lived bad cache pattern would knock out otherwise valid candidates and make routing brittle.

### Option 2: Soft penalty from raw thrift metrics

Chosen. It preserves ranking flexibility, works with the metrics we already collect, and stays aligned with the real goal: nudge cost-aware routing away from traffic classes where cache warming keeps failing.

### Option 3: Global penalty across all routing strategies

Too blunt. `SPEED_OPTIMIZED` and `QUALITY_OPTIMIZED` should not get dragged around by cache behavior when the operator explicitly asked for something else.

## Architecture

### 1. Read thrift feedback once per routing decision

During `AdaptiveRouter.process()`, fetch one runtime thrift snapshot for a recent local-day window and pass it into model evaluation.

Use `get_thrift_metrics_snapshot_for_dates(...)` with a rolling lookback window, default `7` local days including today.

This avoids re-reading the same persisted thrift rollup for every model candidate like a caveman.

### 2. Derive machine-facing penalties from raw buckets

Do **not** use `cache_deadspots` for routing input. That field is top-3 human summary output and is intentionally trimmed.

Instead, compute a penalty directly from raw:

- `cache_efficiency_by_model`
- `cache_efficiency_by_provider`

Bucket selection order:

1. exact model bucket if present
2. provider bucket fallback
3. no penalty if neither exists

### 3. Penalty rules

Penalty should increase when all of these smell bad:

- `cache_write_requests` / `cache_write_request_rate_pct` are non-trivial
- `cache_hit_request_rate_pct` lags far behind write rate
- `reuse_to_write_ratio` is below `1.0`

Suggested penalty inputs:

- write-hit gap ratio
- low reuse depth
- whether the bucket has zero hits

Suggested behavior:

- cap penalty so it nudges, not nukes, model selection
- keep penalty `0.0` when cache warming is already paying off

### 4. Apply only on cost-sensitive paths

- `COST_OPTIMIZED`: apply penalty directly to the cost score
- `ADAPTIVE`:
  - apply when objective is `MINIMIZE_COST`
  - apply when objective is `BALANCE_ALL`
  - skip for `MINIMIZE_TIME`, `MAXIMIZE_QUALITY`, `MAXIMIZE_THROUGHPUT`
- skip for:
  - `PERFORMANCE_BASED`
  - `SPEED_OPTIMIZED`
  - `QUALITY_OPTIMIZED`
  - `LOAD_BALANCED`

### 5. Expose traceable metadata

Each evaluated model should carry thrift-feedback metadata so operators can see why a score moved:

- `penalty`
- `source` (`model`, `provider`, or `none`)
- `lookback_days`
- `window_start`
- `window_end`
- `bucket_summary` (minimal subset only)

The adaptive-model-selection handler should surface this under `routing_metrics.thrift_feedback` for the selected model.

## Data Flow

1. `AdaptiveRouter.process()` computes routing window dates
2. Fetch thrift metrics once for that window
3. `_evaluate_models()` passes the snapshot to each candidate evaluation
4. `_evaluate_single_model()` derives candidate penalty from model/provider cache buckets
5. `_calculate_strategy_score()` applies the penalty only for cost-sensitive strategies
6. Selected evaluation metadata is stored in `RoutingDecision.metadata`
7. `_adaptive_model_selection_impl()` returns selected thrift feedback in `routing_metrics`

## Error Handling

- If thrift metrics lookup fails or returns malformed bucket data:
  - log at debug/warning level
  - treat as `no penalty`
- If no matching model/provider bucket exists:
  - treat as `no penalty`
- If the lookback window is empty:
  - treat as `no penalty`

The router must still make a routing decision even when thrift observability is asleep at the wheel.

## Configuration

Keep the first slice local to router config:

- `thrift_feedback_enabled`: `True`
- `thrift_feedback_lookback_days`: `7`
- `thrift_penalty_cap`: around `0.35`

No new env vars yet. If this proves useful, policy/env wiring can come later.

## Affected Areas

- `src/openrouter_mcp/collective_intelligence/adaptive_router.py`
  - thrift snapshot lookup
  - penalty helper(s)
  - strategy score integration
  - routing metadata
- `src/openrouter_mcp/handlers/collective_intelligence.py`
  - expose selected-model thrift feedback in response
- `tests/test_collective_intelligence/test_adaptive_router.py`
  - penalty math and strategy gating
- `tests/test_collective_intelligence_regression.py`
  - handler regression
- `tests/test_collective_intelligence_mocked.py`
  - mocked handler smoke assertions
- `tests/contracts/schemas/adaptive_model_selection.response.schema.json`
  - optional `routing_metrics.thrift_feedback`

## Risks

- stale thrift data could keep punishing a provider after traffic changes
- penalty could overpower baseline cost score and create weird routing inversions
- exposing too much bucket detail in handler output could bloat the response

## Mitigations

- bound routing feedback to a recent local-day window
- cap penalty strength
- keep handler output to selected-model thrift feedback only
- leave non-cost strategies untouched
