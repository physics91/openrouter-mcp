# Assurance Testing Policy

This document defines the 99.9% reliability-oriented testing policy introduced
for the repository.

## Gate Layers

### PR Required Gates
- `Required Assurance Gate` workflow
- `Required Static Checks` workflow
- Trigger: `pull_request` targeting `main` or `develop`

### Advisory Gates
- `Assurance Extended` workflow (`advisory-static-analysis`, `advisory-performance`)
- Default trigger: `workflow_dispatch`
- PR opt-in trigger: add label `ci:extended` on PR targeting `main` or `develop`

### Scheduled Gates
- Nightly live API canary (`0 18 * * *` UTC, excludes `performance/stress/quality`)
- Weekly mutation sample (`0 19 * * 0` UTC)
- Legacy CI daily schedule (`ci.yml`: `0 2 * * *` UTC)
- Legacy coverage weekly schedule (`test-coverage.yml`: `0 3 * * 0` UTC)

## Test Markers (Pytest)

- `unit`: Fast, isolated logic tests
- `contract`: MCP tool I/O contract tests with JSON Schema
- `property`: Invariant and monotonic property tests
- `replay`: Deterministic replay tests with fixed fixtures
- `mutation`: Mutation-focused tests (reserved)
- `live_api`: Live API tests (scheduled only)
- `chaos`: Fault-injection resilience tests (reserved)
- `security`: Security-focused checks

## Local Command

```bash
npm run test:assurance
```

The command runs:
1. Python assurance slices (`unit/contract/property/replay`)
2. Node security tests (`npm run test:security`)
3. Coverage gate (requires `pytest-cov`; missing dependency fails fast)

## Local Hooks

- Installed `pre-push` hooks are intentionally limited to smoke coverage.
- Advisory static analysis stays opt-in, matching the non-required CI posture:
  - `pre-commit run --hook-stage manual flake8-advisory --all-files`
  - `pre-commit run --hook-stage manual mypy-advisory --all-files`
  - `pre-commit run --hook-stage manual bandit-advisory --all-files`
  - `pre-commit run --hook-stage manual pylint-advisory --all-files`
