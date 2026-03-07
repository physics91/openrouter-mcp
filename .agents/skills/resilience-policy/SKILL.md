---
name: resilience-policy
description: Use when changing concurrency limits, quota rules, circuit breakers, cleanup behavior, or other high-risk resilience policies in the collective-intelligence paths
---

# Resilience Policy

## Overview

Use this skill for changes where correctness depends on operational invariants rather than one user-facing feature.
It keeps concurrency, quota, circuit-breaker, and cleanup edits tied to explicit invariants and targeted verification.

## Primary Files In Scope

- `src/openrouter_mcp/collective_intelligence/operational_controls.py`
- `src/openrouter_mcp/collective_intelligence/consensus_engine.py`
- `src/openrouter_mcp/collective_intelligence/collaborative_solver.py`
- `src/openrouter_mcp/collective_intelligence/lifecycle_manager.py`
- `src/openrouter_mcp/handlers/mcp_benchmark.py`
- `tests/test_operational_controls.py`
- `tests/test_lifecycle_manager.py`
- `tests/test_collective_intelligence/`

## Required Invariants

- Every acquired slot, semaphore, or limiter path must release symmetrically.
- In-memory history and buffers must stay bounded.
- Failure counters and circuit state must have explicit reset or recovery semantics.
- Cleanup and shutdown paths must still run when execution errors or cancellations happen.
- Degraded behavior must be explicit; do not silently swallow policy failures.

## Change Workflow

1. Name the invariant being changed before editing code.
2. Add or adjust the failing test first.
3. Keep the implementation minimal and policy-focused.
4. Run the narrowest targeted tests that prove the invariant.
5. If the change touches shared execution behavior, widen verification to assurance or the most relevant integration slice.

## Verification Targets

Start with targeted tests such as:

```
python3 -m pytest tests/test_operational_controls.py -v
python3 -m pytest tests/test_lifecycle_manager.py -v
python3 -m pytest tests/test_collective_intelligence/ -v
```

Escalate when needed:

```
python3 run_tests.py integration -v
python3 run_tests.py assurance -v
```

If the policy change affects replay, property, or performance behavior, run the relevant suite instead of assuming the narrower tests are enough.

## Red Flags

- Adding retries, delays, or larger limits without naming the invariant they protect.
- Modifying cleanup paths without verifying shutdown behavior.
- Touching concurrency policy without checking release symmetry.
- Relying on one happy-path integration test for a policy change.

## Done Definition

- The changed invariant is explicit.
- Targeted tests were chosen based on the touched policy.
- Cleanup, release, and recovery behavior were considered, not assumed.
- Wider assurance was run when the change crossed subsystem boundaries.
