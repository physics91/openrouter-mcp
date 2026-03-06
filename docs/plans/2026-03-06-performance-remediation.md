# OpenRouter Performance Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** baseline 테스트를 복구한 뒤 cache, consensus, benchmark, iterative 경로의 주요 성능 병목을 순차적으로 제거한다.

**Architecture:** 먼저 FastMCP public API 기반으로 테스트를 안정화해 검증 토대를 복구한다. 그 다음 공용 상태 경쟁(cache), CPU 고비용(consensus), 직렬 실행(benchmark), tail latency guard(iterative/concurrency) 순으로 작은 패치를 누적한다.

**Tech Stack:** Python 3.12, pytest, FastMCP, asyncio

---

### Task 1: FastMCP Baseline Test Compatibility

**Files:**
- Modify: `tests/test_mcp_integration.py`
- Modify: `tests/test_mcp_server_fixed.py`

**Step 1: Keep the failing regression visible**

Run:
```bash
python3 run_tests.py quick -v
```

Expected:
- `FastMCP`에 `get_tools` 또는 `_tool_manager`가 없어 실패

**Step 2: Add public API helpers in tests**

- `await mcp.list_tools()`를 `{tool.name: tool}` dict로 바꾸는 helper 추가
- private `_tool_manager` 접근 제거

**Step 3: Run targeted tests**

Run:
```bash
python3 -m pytest tests/test_mcp_integration.py tests/test_mcp_server_fixed.py -v
```

Expected:
- 두 파일이 현재 FastMCP API 기준으로 통과

**Step 4: Re-run quick baseline**

Run:
```bash
python3 run_tests.py quick -v
```

Expected:
- quick suite green

### Task 2: Cache Refresh Coalescing

**Files:**
- Modify: `src/openrouter_mcp/models/cache.py`
- Modify: `tests/test_models_cache.py`
- Modify: `tests/test_concurrent_client.py`

**Step 1: Write failing concurrency test**

- 만료된 cache에 동시 `get_models()` 여러 호출 시 fetch가 1번만 일어나야 함

**Step 2: Verify red**

Run:
```bash
python3 -m pytest tests/test_models_cache.py -k coalesc -v
```

**Step 3: Implement in-flight refresh dedupe**

- shared future 또는 lock 사용
- 예외 시 상태 정리

**Step 4: Verify green**

Run:
```bash
python3 -m pytest tests/test_models_cache.py tests/test_concurrent_client.py -v
```

### Task 3: Semantic Grouping Fast-Path

**Files:**
- Modify: `src/openrouter_mcp/collective_intelligence/consensus_engine.py`
- Modify: `src/openrouter_mcp/collective_intelligence/semantic_similarity.py`
- Modify: `tests/test_consensus_semantic_grouping.py`
- Modify: `tests/test_semantic_similarity.py`

**Step 1: Add failing perf-guard test**
- 큰 입력에서 불필요한 pairwise 호출 수를 줄였는지 검증

**Step 2: Verify red**

Run:
```bash
python3 -m pytest tests/test_consensus_semantic_grouping.py tests/test_semantic_similarity.py -v
```

**Step 3: Implement fast-path**
- cheap prefilter 또는 representative comparison 도입

**Step 4: Verify green**

Run:
```bash
python3 -m pytest tests/test_consensus_semantic_grouping.py tests/test_semantic_similarity.py tests/test_collective_intelligence/test_consensus_engine.py -v
```

### Task 4: Benchmark Parallelization

**Files:**
- Modify: `src/openrouter_mcp/handlers/benchmark.py`
- Modify: `src/openrouter_mcp/handlers/mcp_benchmark.py`
- Modify: `tests/test_benchmark.py`
- Modify: `tests/test_mcp_benchmark.py`

**Step 1: Add failing wrapper-path test**
- MCP wrapper가 병렬 경로를 사용할 수 있어야 함

**Step 2: Verify red**

Run:
```bash
python3 -m pytest tests/test_benchmark.py tests/test_mcp_benchmark.py -v
```

**Step 3: Implement bounded parallel path**
- 기본 동시성 보수적 설정
- 기존 직렬 fallback 유지 여부 검토

**Step 4: Verify green**

Run:
```bash
python3 -m pytest tests/test_benchmark.py tests/test_mcp_benchmark.py tests/test_benchmark_handlers.py -v
```

### Task 5: Iterative Guard and Timeout Budget

**Files:**
- Modify: `src/openrouter_mcp/collective_intelligence/operational_controls.py`
- Modify: `src/openrouter_mcp/collective_intelligence/collaborative_solver.py`
- Modify: `tests/test_operational_controls.py`
- Modify: `tests/test_collective_intelligence_mocked.py`

**Step 1: Add failing timeout/guard test**

**Step 2: Verify red**

Run:
```bash
python3 -m pytest tests/test_operational_controls.py tests/test_collective_intelligence_mocked.py -v
```

**Step 3: Implement wait budget and clearer iterative termination**

**Step 4: Verify green**

Run:
```bash
python3 -m pytest tests/test_operational_controls.py tests/test_collective_intelligence_mocked.py tests/test_collective_comprehensive.py -v
```

### Task 6: Final Verification

**Files:**
- No code changes expected

**Step 1: Run static checks**

Run:
```bash
python3 -m ruff check src/ tests/
python3 -m black --check src/ tests/
python3 -m isort --check-only src/ tests/
```

**Step 2: Run assurance-relevant tests**

Run:
```bash
python3 run_tests.py quick -v
python3 -m pytest tests/test_models_cache.py tests/test_concurrent_client.py tests/test_mcp_benchmark.py tests/test_collective_intelligence/test_consensus_engine.py tests/test_operational_controls.py -v
```

**Step 3: Run broader assurance if time allows**

Run:
```bash
python3 run_tests.py assurance -v
```
