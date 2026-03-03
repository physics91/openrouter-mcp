# Assurance Testing Policy

This document defines the 99.9% reliability-oriented testing policy introduced
for the repository.

## Gate Layers

### PR Required Gates
- `Required Assurance Gate` workflow
- `Required Static Checks` workflow

### Advisory Gates
- `Assurance Extended` workflow (`advisory-static-analysis`, `advisory-performance`)

### Scheduled Gates
- Nightly live API canary (`0 18 * * *` UTC, excludes `performance/stress/quality`)
- Weekly mutation sample (`0 19 * * 0` UTC)

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
