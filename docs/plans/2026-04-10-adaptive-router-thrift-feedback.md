# Adaptive Router Thrift Feedback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Teach `AdaptiveRouter` to down-rank cache-deadspot providers/models on cost-sensitive routing paths using recent runtime thrift metrics

**Architecture:** Fetch one recent runtime thrift snapshot per routing decision, derive a bounded penalty from raw provider/model cache-efficiency buckets, and apply it only to `COST_OPTIMIZED` plus cost-leaning `ADAPTIVE` objectives. Store the selected model's thrift-feedback metadata in the routing decision and expose it from the adaptive-model-selection handler.

**Tech Stack:** Python, pytest, JSON schema contracts, runtime thrift metrics, collective-intelligence router

---

### Task 1: Add failing router tests for thrift-penalty gating

**Files:**
- Modify: `tests/test_collective_intelligence/test_adaptive_router.py`

**Step 1: Write the failing test**

- Add a cost-optimized test where two otherwise similar models differ only by thrift deadspot penalty and the healthy one should score higher
- Add an adaptive test where `MINIMIZE_COST` applies the penalty
- Add an adaptive test where `MAXIMIZE_QUALITY` ignores the penalty
- Add a non-cost strategy test proving `SPEED_OPTIMIZED` or `PERFORMANCE_BASED` stays unchanged

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_collective_intelligence/test_adaptive_router.py -k thrift`

Expected: FAIL because router does not read runtime thrift metrics or apply penalties yet

### Task 2: Add failing selection-path test

**Files:**
- Modify: `tests/test_collective_intelligence/test_adaptive_router.py`

**Step 1: Write the failing test**

- Add a routing test where a nominally cheaper deadspot model loses to a slightly pricier healthy model once thrift penalty is applied

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_collective_intelligence/test_adaptive_router.py -k deadspot`

Expected: FAIL because routing still ignores thrift feedback

### Task 3: Implement router thrift-feedback helpers

**Files:**
- Modify: `src/openrouter_mcp/collective_intelligence/adaptive_router.py`

**Step 1: Write minimal implementation**

- Add router config keys:
  - `thrift_feedback_enabled`
  - `thrift_feedback_lookback_days`
  - `thrift_penalty_cap`
- Fetch one recent thrift snapshot in `process()` using `get_thrift_metrics_snapshot_for_dates(...)`
- Pass that snapshot into `_evaluate_models()` / `_evaluate_single_model()`
- Add helper(s) to:
  - locate model or provider bucket
  - compute bounded penalty
  - return metadata (`source`, `penalty`, `window_start`, `window_end`, `lookback_days`)
- Apply penalty only to:
  - `RoutingStrategy.COST_OPTIMIZED`
  - `RoutingStrategy.ADAPTIVE` with `MINIMIZE_COST` or `BALANCE_ALL`
- Keep other strategies untouched
- Store selected-model thrift feedback in `RoutingDecision.metadata`

**Step 2: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_collective_intelligence/test_adaptive_router.py -k "thrift or deadspot"`

Expected: PASS

### Task 4: Expose selected thrift feedback from handler

**Files:**
- Modify: `src/openrouter_mcp/handlers/collective_intelligence.py`
- Modify: `tests/test_collective_intelligence_regression.py`
- Modify: `tests/test_collective_intelligence_mocked.py`
- Modify: `tests/contracts/schemas/adaptive_model_selection.response.schema.json`
- Modify: `tests/contracts/test_collective_contracts.py`

**Step 1: Write the failing test**

- Add handler/regression test asserting `routing_metrics.thrift_feedback` is present when cost-sensitive routing uses thrift penalty
- Add schema expectation for optional `routing_metrics.thrift_feedback`

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_collective_intelligence_regression.py tests/test_collective_intelligence_mocked.py tests/contracts/test_collective_contracts.py -k adaptive_model_selection`

Expected: FAIL because handler does not expose thrift feedback yet

**Step 3: Write minimal implementation**

- Include selected model thrift metadata under `routing_metrics.thrift_feedback`
- Keep payload compact:
  - `penalty`
  - `source`
  - `lookback_days`
  - `window_start`
  - `window_end`
  - small bucket summary only

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_collective_intelligence_regression.py tests/test_collective_intelligence_mocked.py tests/contracts/test_collective_contracts.py -k adaptive_model_selection`

Expected: PASS

### Task 5: Update docs for adaptive routing feedback

**Files:**
- Modify: `docs/API.md`
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `tests/test_project_consistency.py`

**Step 1: Write the failing test**

- Add consistency assertions for adaptive-model-selection thrift feedback wording

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_project_consistency.py`

Expected: FAIL because docs do not mention router thrift feedback yet

**Step 3: Write minimal implementation**

- Document that `adaptive_model_selection` may include `routing_metrics.thrift_feedback`
- Explain that the signal only affects cost-sensitive routing paths

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_project_consistency.py`

Expected: PASS

### Task 6: Run canonical verification

**Files:**
- No code changes

**Step 1: Run unit suite**

Run: `python3 run_tests.py unit -v`

Expected: PASS

**Step 2: Run assurance suite**

Run: `python3 run_tests.py assurance -v`

Expected: PASS with coverage still above threshold
