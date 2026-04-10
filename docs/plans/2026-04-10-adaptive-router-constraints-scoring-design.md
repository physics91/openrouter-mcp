# Adaptive Router Constraints And Scoring Design

## Context

`adaptive_model_selection` advertises two knobs:

- `constraints`
- `performance_requirements`

But the current router mostly treats them like decorative JSON. That means callers can ask for `max_cost`, `preferred_provider`, or stronger `accuracy` weighting and still get whatever the baseline strategy was going to do anyway.

That is worse than not exposing the knobs at all. The API sounds deterministic, but the router is mostly shrugging.

## Decision

Use a hybrid interpretation:

- hard filters for true guardrails
- soft preferences for `preferred_*` hints
- weighted scoring for `performance_requirements`

Specifically:

- hard filters:
  - `max_cost`
  - `excluded_provider`
  - `required_capabilities`
  - `min_context_length`
- soft preferences:
  - `preferred_provider`
  - `preferred_model_family`
- weighted scoring:
  - `performance_requirements.accuracy`
  - `performance_requirements.speed`
  - `performance_requirements.cost`

If hard filters remove every candidate, routing should fail explicitly instead of silently pretending the constraints never existed.

## Why This Approach

### Option 1: Treat everything as a hard filter

Too brittle. `preferred_provider=openai` would become an accidental kill switch, and slightly noisy numeric hints would collapse the candidate set to zero.

### Option 2: Treat everything as soft scoring

Rejected. Then `constraints` is basically a lie. A caller can say `max_cost=0.001` and still get a pricier model because the router felt cute that day.

### Option 3: Hybrid guardrail + preference + scoring

Chosen. It matches the names of the fields, keeps routing flexible where it should be flexible, and makes failure explicit where the caller asked for a real boundary.

## Constraint Semantics

### Hard filters

Apply before model ranking:

1. `max_cost`
   - Compare against predicted request cost
   - Reject models whose predicted cost exceeds the ceiling
2. `excluded_provider`
   - Reject provider matches case-insensitively
3. `required_capabilities`
   - Support enum-style capability names such as `reasoning`, `accuracy`, `code`, `math`, `multimodal`
   - Require capability score to be greater than `0`
4. `min_context_length`
   - Reject models whose `context_length` is too small

### Soft preferences

Apply after base strategy score:

1. `preferred_provider`
   - Add a bounded boost to matching providers
2. `preferred_model_family`
   - Match case-insensitively against `model_id` and `name`
   - Examples:
     - `gpt-4`
     - `claude-3`
     - `gemini`

These are preferences, not promises.

## Performance Requirement Semantics

`performance_requirements` should be treated as score weights, not filters.

Supported normalized keys:

- `accuracy`
- `speed`
- `cost`

Alias handling can stay minimal:

- `quality` -> `accuracy`
- `latency` -> `speed`

Unknown keys should be ignored, not exploded.

Normalization rules:

- keep only numeric positive values
- normalize so the weights sum to `1.0`
- if nothing valid remains, use strategy defaults

These weights should influence:

- `RoutingStrategy.ADAPTIVE`
- `RoutingStrategy.PERFORMANCE_BASED`

Other strategies keep their explicit semantics:

- `COST_OPTIMIZED`
- `SPEED_OPTIMIZED`
- `QUALITY_OPTIMIZED`
- `LOAD_BALANCED`

Those paths should only accept soft preference adjustments, not a full score rewrite.

## Architecture

### 1. Normalize routing policy input once per task

Add helpers in `AdaptiveRouter` that parse and normalize:

- hard filters
- soft preferences
- performance weights

Do this once per routing decision, then pass the normalized policy into candidate evaluation.

### 2. Filter candidates before ranking

Before scoring a model, determine whether it violates any hard filter.

Each filtered candidate should record machine-readable reasons such as:

- `max_cost`
- `excluded_provider`
- `required_capabilities`
- `min_context_length`

Filtered candidates must not continue into score ranking.

### 3. Apply weighted scoring and preference boosts

For surviving candidates:

1. compute predicted metrics
2. compute base strategy score
3. apply performance-requirement reweighting when the strategy supports it
4. apply bounded preference boosts
5. apply existing thrift feedback penalty where relevant

This keeps cost deadspot feedback and caller intent in the same pipeline instead of bolting on another cursed side path.

### 4. Expose routing metadata

Return enough metadata for operators to tell what happened:

- `constraints_applied`
- `constraints_unmet`
- `filtered_candidates`
- `performance_weights`
- `preference_matches`

For the selected model, surface matched preferences and active weights under `routing_metrics`.

When all candidates are filtered out, raise a routing error that names the unmet constraint classes.

## Data Flow

1. Handler builds `TaskContext` with raw `constraints` and `performance_requirements`
2. `AdaptiveRouter.process()` normalizes routing policy once
3. Router filters candidates using hard constraints
4. Surviving candidates are scored with strategy logic
5. Supported strategies apply performance-weight overrides
6. Soft preferences add bounded boosts
7. Existing thrift penalty still applies on cost-sensitive paths
8. Selected-model metadata is returned in `routing_metrics`

## Error Handling

- invalid numeric constraint values:
  - ignore with warning-level logging
- unknown capability names:
  - ignore with warning-level logging
- empty candidate set after filtering:
  - raise `ValueError` with constraint summary
- unknown performance keys:
  - ignore silently

Routing must fail loudly when guardrails remove everything, not quietly route around the user's ask like some bargain-bin autocomplete.

## Response Shape

Extend `routing_metrics` with compact policy metadata:

- `constraints_applied`
- `constraints_unmet`
- `filtered_candidates`
- `performance_weights`
- `preference_matches`

Keep this machine-readable and compact. No giant candidate dump.

## Affected Areas

- `src/openrouter_mcp/collective_intelligence/adaptive_router.py`
  - constraint normalization
  - hard filtering
  - weighted scoring
  - preference boosts
  - metadata generation
- `src/openrouter_mcp/handlers/collective_intelligence.py`
  - adaptive-model-selection response metadata
- `tests/test_collective_intelligence/test_adaptive_router.py`
  - router unit coverage
- `tests/test_collective_intelligence_regression.py`
  - handler regression
- `tests/test_collective_intelligence_mocked.py`
  - mocked handler coverage
- `tests/contracts/schemas/adaptive_model_selection.response.schema.json`
  - routing-metadata schema additions
- `tests/contracts/test_collective_contracts.py`
  - response contract coverage
- `docs/API.md`
- `docs/TROUBLESHOOTING.md`

## Risks

- over-filtering could turn harmless hints into frequent routing failures
- score boosts could overpower the base strategy if left unbounded
- noisy input could create inconsistent policy metadata

## Mitigations

- keep hard filters limited to true guardrails only
- cap preference boosts
- normalize weights once per routing decision
- ignore unknown keys instead of failing the request
- emit explicit `constraints_unmet` metadata when filters eliminate all models
