# Runtime Thrift Persistence Design

## Context

`get_usage_stats()` currently merges provider usage data with process-local runtime thrift counters. That works only while one process stays alive and does not respect `start_date` / `end_date`. After restart, thrift savings disappear. With date filters, provider usage is time-bounded but thrift data is not.

## Decision

Persist runtime thrift counters into a daily rollup JSON file under `.cache/`, keyed by local calendar date (`YYYY-MM-DD`). Every runtime thrift recording path will continue updating the in-memory collector and will also update the current day bucket on disk.

`get_usage_stats()` will build thrift metadata from:

- date-filtered persisted rollups when `start_date` and/or `end_date` are supplied
- persisted rollups plus the current in-memory day bucket for undated requests

## Why This Approach

### Option 1: Single snapshot file

Too weak. It survives restart but cannot answer date-bounded thrift summaries.

### Option 2: Daily rollup JSON

Chosen. It matches `get_usage_stats` date filtering, keeps implementation small, and fits the current file-based persistence style already used elsewhere in the repo.

### Option 3: SQLite event log

Too much machinery for the current scope. Useful later if per-request forensic analysis becomes necessary.

## Storage Model

- File path: `.cache/runtime_thrift_metrics.json`
- Root shape:
  - `version`
  - `days`
    - `YYYY-MM-DD`
      - full thrift metrics snapshot for that day
- Writes are atomic (`tmp` + `os.replace`)
- Corrupt files reset to an empty store with a warning log

## Read Semantics

- Date range is inclusive on both ends
- Dates are interpreted in local server time
- If no dates are provided, the response includes all persisted days plus any in-memory metrics for the current local day that have not yet been reloaded from disk

## Affected Areas

- `src/openrouter_mcp/runtime_thrift/metrics.py`
  - add persistence layer, daily aggregation helpers, date-range snapshot helpers
- `src/openrouter_mcp/config/constants.py`
  - add default persistence path constant
- `src/openrouter_mcp/handlers/chat.py`
  - make `get_usage_stats()` use date-aware thrift snapshots
- `tests/test_runtime_thrift/*`
  - persistence, corruption recovery, date filter behavior
- `tests/test_handlers/test_chat_handler.py`
  - usage stats thrift/date-range contract
- docs
  - explain that thrift summaries are persisted daily and date-aligned

## Risks

- Double-counting current-day metrics if persisted data and live memory are merged incorrectly
- Hidden timezone confusion if docs fail to say “local day”
- Disk write churn if every metric write flushes immediately

## Mitigations

- Keep one persisted collector and one request-local collector; never merge request-local into persisted rollups
- For undated reads, merge persisted snapshot with in-memory current-day delta only once
- Reuse the repo’s existing atomic JSON persistence pattern
- Document local-date semantics explicitly
