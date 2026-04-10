# Adaptive Router Constraints And Scoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `adaptive_model_selection` actually honor hard routing constraints, soft provider/model preferences, and weighted performance requirements

**Architecture:** Normalize routing policy once per request, filter candidates using hard guardrails, then rank survivors with existing strategy logic plus weighted scoring and bounded preference boosts. Return compact routing metadata so callers can see which constraints and preferences affected selection.

**Tech Stack:** Python, pytest, JSON schema contracts, collective-intelligence router, adaptive-model-selection handler

---

### Task 1: Add failing unit tests for hard constraints

**Files:**
- Modify: `tests/test_collective_intelligence/test_adaptive_router.py`

**Step 1: Write the failing test**

- Add unit tests proving:
  - `max_cost` filters out over-budget models
  - `excluded_provider` filters matching providers
  - `required_capabilities` filters models without requested capabilities
  - `min_context_length` filters undersized models
- Add a failure-path test where every candidate is filtered and routing raises an explicit constraints error

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_collective_intelligence/test_adaptive_router.py -k "max_cost or excluded_provider or required_capabilities or min_context_length or constraints error"`

Expected: FAIL because router does not filter on these constraints yet

### Task 2: Add failing unit tests for soft preferences and weighted scoring

**Files:**
- Modify: `tests/test_collective_intelligence/test_adaptive_router.py`

**Step 1: Write the failing test**

- Add unit tests proving:
  - `preferred_provider` boosts a matching provider without hard-filtering others
  - `preferred_model_family` boosts case-insensitive family matches in `model_id` or `name`
  - `performance_requirements={"accuracy": ..., "speed": ..., "cost": ...}` changes adaptive/performance-based ranking
  - unsupported strategies keep their core semantics

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_collective_intelligence/test_adaptive_router.py -k "preferred_provider or preferred_model_family or performance_requirements"`

Expected: FAIL because router does not yet normalize preferences or performance weights

### Task 3: Implement normalized routing policy in the router

**Files:**
- Modify: `src/openrouter_mcp/collective_intelligence/adaptive_router.py`

**Step 1: Write minimal implementation**

- Add helpers to normalize:
  - hard constraints
  - soft preferences
  - performance weights
- Support aliases:
  - `quality` -> `accuracy`
  - `latency` -> `speed`
- Ignore unknown keys and malformed values safely
- Carry normalized routing policy through the routing flow

**Step 2: Run targeted tests**

Run: `python3 -m pytest -q tests/test_collective_intelligence/test_adaptive_router.py -k "preferred_provider or preferred_model_family or performance_requirements or max_cost or excluded_provider or required_capabilities or min_context_length"`

Expected: some tests still FAIL until filtering/scoring is wired end-to-end

### Task 4: Wire hard filtering and score adjustments end-to-end

**Files:**
- Modify: `src/openrouter_mcp/collective_intelligence/adaptive_router.py`

**Step 1: Write minimal implementation**

- Filter candidates before ranking using normalized hard constraints
- Raise explicit error when no candidates survive
- Apply weighted scoring to:
  - `RoutingStrategy.ADAPTIVE`
  - `RoutingStrategy.PERFORMANCE_BASED`
- Apply bounded boosts for:
  - `preferred_provider`
  - `preferred_model_family`
- Keep thrift deadspot penalties working on cost-sensitive paths
- Record compact metadata:
  - `constraints_applied`
  - `constraints_unmet`
  - `filtered_candidates`
  - `performance_weights`
  - `preference_matches`

**Step 2: Run tests to verify it passes**

Run: `python3 -m pytest -q tests/test_collective_intelligence/test_adaptive_router.py -k "preferred_provider or preferred_model_family or performance_requirements or max_cost or excluded_provider or required_capabilities or min_context_length or constraints error"`

Expected: PASS

### Task 5: Add failing handler and contract coverage

**Files:**
- Modify: `src/openrouter_mcp/handlers/collective_intelligence.py`
- Modify: `tests/test_collective_intelligence_regression.py`
- Modify: `tests/test_collective_intelligence_mocked.py`
- Modify: `tests/contracts/schemas/adaptive_model_selection.response.schema.json`
- Modify: `tests/contracts/test_collective_contracts.py`

**Step 1: Write the failing test**

- Add handler tests asserting adaptive-model-selection responses expose:
  - `routing_metrics.constraints_applied`
  - `routing_metrics.filtered_candidates`
  - `routing_metrics.performance_weights`
  - `routing_metrics.preference_matches`
- Add contract/schema coverage for the new routing metadata

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_collective_intelligence_regression.py tests/test_collective_intelligence_mocked.py tests/contracts/test_collective_contracts.py -k adaptive_model_selection`

Expected: FAIL because handler/schema do not expose the new metadata yet

### Task 6: Implement handler/schema/docs updates

**Files:**
- Modify: `src/openrouter_mcp/handlers/collective_intelligence.py`
- Modify: `tests/contracts/schemas/adaptive_model_selection.response.schema.json`
- Modify: `docs/API.md`
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `tests/test_project_consistency.py`

**Step 1: Write minimal implementation**

- Return compact routing-policy metadata in `routing_metrics`
- Document hard-filter vs soft-preference semantics for `adaptive_model_selection`
- Add troubleshooting guidance for:
  - why all models were filtered
  - how preference boosts interact with base routing

**Step 2: Run tests to verify it passes**

Run: `python3 -m pytest -q tests/test_collective_intelligence_regression.py tests/test_collective_intelligence_mocked.py tests/contracts/test_collective_contracts.py tests/test_project_consistency.py -k adaptive_model_selection`

Expected: PASS

### Task 7: Run canonical verification

**Files:**
- No code changes

**Step 1: Run unit suite**

Run: `python3 run_tests.py unit -v`

Expected: PASS

**Step 2: Run assurance suite**

Run: `python3 run_tests.py assurance -v`

Expected: PASS with coverage still above threshold
