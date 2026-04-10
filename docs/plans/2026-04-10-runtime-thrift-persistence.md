# Runtime Thrift Persistence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist runtime thrift savings by local day so `get_usage_stats` returns thrift summaries that survive restarts and respect `start_date` / `end_date`

**Architecture:** Extend the runtime thrift collector with a file-backed daily rollup store. Keep request-scoped thrift metrics in memory only, but mirror process-wide thrift updates into the current day bucket. `get_usage_stats` will read filtered thrift snapshots from the persisted rollups instead of blindly using process lifetime counters.

**Tech Stack:** Python, dataclasses, JSON persistence, atomic file replacement, pytest

---

### Task 1: Add failing persistence tests

**Files:**
- Modify: `tests/test_runtime_thrift/test_metrics.py`
- Modify: `tests/test_handlers/test_chat_handler.py`

**Step 1: Write the failing test**

- Add a metrics-level test proving day-bucket data survives a collector reload and can be filtered by date range
- Add a handler-level test proving `get_usage_stats(start_date, end_date)` returns thrift metadata from the matching persisted day only

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_runtime_thrift/test_metrics.py tests/test_handlers/test_chat_handler.py`

Expected: FAIL because no persisted daily rollup or date-filtered thrift snapshot exists yet

**Step 3: Write minimal implementation**

- none yet

**Step 4: Run test to verify it still fails for the right reason**

Run: `python3 -m pytest -q tests/test_runtime_thrift/test_metrics.py tests/test_handlers/test_chat_handler.py`

Expected: FAIL on missing behavior, not syntax/import errors

### Task 2: Add daily thrift persistence

**Files:**
- Modify: `src/openrouter_mcp/config/constants.py`
- Modify: `src/openrouter_mcp/runtime_thrift/metrics.py`

**Step 1: Write the failing test**

- Add corruption-recovery and current-day merge tests in `tests/test_runtime_thrift/test_metrics.py`

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_runtime_thrift/test_metrics.py`

Expected: FAIL because the collector does not persist or recover

**Step 3: Write minimal implementation**

- Add default path constant for thrift persistence
- Add file-backed daily rollup store with atomic save/load
- Add helpers to snapshot all days or a date-bounded subset
- Mirror process-wide `record_*` calls into the persisted day bucket

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_runtime_thrift/test_metrics.py`

Expected: PASS

### Task 3: Wire date-aware thrift stats into `get_usage_stats`

**Files:**
- Modify: `src/openrouter_mcp/handlers/chat.py`
- Test: `tests/test_handlers/test_chat_handler.py`

**Step 1: Write the failing test**

- Add a test where provider usage is filtered to one day and thrift summary must match only that day’s persisted rollup

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_handlers/test_chat_handler.py::TestChatHandler::test_get_usage_stats_uses_date_filtered_thrift_rollup`

Expected: FAIL because `get_usage_stats()` still uses process-global thrift snapshot

**Step 3: Write minimal implementation**

- Replace the global thrift snapshot call with a date-aware persisted snapshot lookup

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_handlers/test_chat_handler.py -k thrift`

Expected: PASS

### Task 4: Update docs and consistency tests

**Files:**
- Modify: `docs/API.md`
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `docs/USAGE_GUIDE_KR.md`
- Modify: `docs/FAQ.md`
- Modify: `tests/test_project_consistency.py`

**Step 1: Write the failing test**

- Add consistency assertions for persisted daily thrift/date-aligned usage wording

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_project_consistency.py`

Expected: FAIL because docs do not mention daily persistence/date alignment yet

**Step 3: Write minimal implementation**

- Document local-day rollup persistence and filtered thrift behavior in all user-facing docs

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_project_consistency.py`

Expected: PASS

### Task 5: Run canonical verification

**Files:**
- No code changes

**Step 1: Run unit suite**

Run: `python3 run_tests.py unit -v`

Expected: PASS

**Step 2: Run assurance suite**

Run: `python3 run_tests.py assurance -v`

Expected: PASS with coverage still above threshold
