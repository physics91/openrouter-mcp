# Runtime Thrift Cache Deadspots Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `cache_deadspots` to `thrift_summary` so operators can see which providers/models are warming prompt cache without converting that warming into meaningful reuse

**Architecture:** Extend the summary layer only. Reuse the existing provider/model cache-efficiency breakdowns, derive a heuristic “deadspot” ranking from those buckets, and expose the result in handler responses and docs. No upstream API changes and no new persisted fields are needed.

**Tech Stack:** Python, pytest, Markdown docs

---

### Task 1: Add failing summary tests

**Files:**
- Modify: `tests/test_runtime_thrift/test_response_metadata.py`
- Modify: `tests/test_handlers/test_chat_handler.py`

**Step 1: Write the failing test**

- Add a summary-level test proving that write-heavy / reuse-poor buckets appear in `cache_deadspots`
- Add a handler-level contract test proving `get_usage_stats()` exposes `cache_deadspots`

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_runtime_thrift/test_response_metadata.py tests/test_handlers/test_chat_handler.py -k deadspot`

Expected: FAIL because `cache_deadspots` does not exist yet

### Task 2: Implement deadspot ranking

**Files:**
- Modify: `src/openrouter_mcp/runtime_thrift/summary.py`

**Step 1: Write minimal implementation**

- Build deadspot entries from existing provider/model cache-efficiency breakdowns
- Rank only buckets with cache writes
- Add `reason` strings for the major failure patterns
- Attach `cache_deadspots` to the final thrift summary

**Step 2: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_runtime_thrift/test_response_metadata.py tests/test_handlers/test_chat_handler.py -k deadspot`

Expected: PASS

### Task 3: Update docs and consistency checks

**Files:**
- Modify: `docs/API.md`
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `docs/USAGE_GUIDE_KR.md`
- Modify: `docs/FAQ.md`
- Modify: `tests/test_project_consistency.py`

**Step 1: Write the failing test**

- Add consistency assertions for `cache_deadspots` and its `reason` field

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_project_consistency.py`

Expected: FAIL because docs do not mention the new field yet

**Step 3: Write minimal implementation**

- Document what `cache_deadspots` means and how to react when it surfaces a provider/model

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_project_consistency.py`

Expected: PASS

### Task 4: Run canonical verification

**Files:**
- No code changes

**Step 1: Run unit suite**

Run: `python3 run_tests.py unit -v`

Expected: PASS

**Step 2: Run assurance suite**

Run: `python3 run_tests.py assurance -v`

Expected: PASS with coverage still above threshold
