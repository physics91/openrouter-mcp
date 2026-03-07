---
name: test
description: Use when running tests, reproducing the repository's assurance gate locally, checking failures, or verifying coverage for openrouter-mcp
---

# Test Skill

## Overview

This repository's canonical local test entrypoint is `python3 run_tests.py <suite> -v`.
Use it even when `package.json` exposes wrappers; the Python runner is the source of truth for local assurance behavior.

## Execution Baseline

- Prefer `python3` for running `run_tests.py` and installing Python dependencies.
- If `python3` is unavailable but `python` exists, use `python` as fallback.
- If pip installation is blocked by externally-managed environment (PEP 668), create and use local `.venv`.
- Default recommendation: `assurance` for PR readiness.
- For the fastest confidence check, use `quick` first and then `regression` if needed.
- Do not substitute `npm run test:assurance` unless the user explicitly wants the npm wrapper.

## Preflight

1. Confirm `python3` and `npm` are available.
2. For `assurance` or `coverage`, ensure `pytest-cov` is installed:
   ```
   python3 -m pip install -r requirements-dev.txt
   ```
3. If pip is externally managed, switch to:
   ```
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements-dev.txt
   ```
4. For the `real` suite, require `OPENROUTER_API_KEY` and remember the run is interactive and billable.

## Canonical Command

```
python3 run_tests.py <suite> -v
```

### Quick Reference

| Suite | Command | When to use |
| --- | --- | --- |
| `assurance` | `python3 run_tests.py assurance -v` | PR gate (unit+contract+property+replay+security, coverage>=70%) |
| `unit` | `python3 run_tests.py unit -v` | Fast isolated checks during development |
| `integration` | `python3 run_tests.py integration -v` | Mocked API integration smoke test |
| `quick` | `python3 run_tests.py quick -v` | Fastest sanity (two regression guards only) |
| `regression` | `python3 run_tests.py regression -v` | Critical bug-prevention tests |
| `coverage` | `python3 run_tests.py coverage -v` | Full HTML coverage report (`htmlcov/index.html`) |
| `all` | `python3 run_tests.py all -v` | Everything except real API tests |
| `real` | `python3 run_tests.py real -v` | Live API calls - requires `OPENROUTER_API_KEY`, consumes credits |

## PR Readiness Runbook

1. If the goal is CI parity, run the `build` skill first.
2. Run:
   ```
   python3 run_tests.py assurance -v
   ```
3. If pytest fails, surface the first failing file or marker group.
4. If pytest passes but Node security fails, call that out separately.
5. If coverage fails, report the threshold and the most obvious low-coverage areas from the output.
6. If the assurance gate is too slow for iteration, fall back to `quick`, `regression`, or a targeted pytest command, then return to `assurance` before claiming readiness.

## Common Failure Modes

- `pytest-cov` missing:
  install `requirements-dev.txt` first.
- `npm` missing:
  `assurance` cannot finish because it runs `npm run test:security` after pytest succeeds.
- `node_modules/` missing:
  allow `run_tests.py` to install them, or run `npm install --no-audit --no-fund` yourself.
- `OPENROUTER_API_KEY` missing:
  `real` will fail fast; use mocked suites instead.
- Marker confusion:
  prefer the named suites in `run_tests.py` unless the user explicitly wants raw `pytest -m ...`.

## Flags

- `-v`: Always include for readable output.
- `--no-cov`: Use only for debugging when speed is more important than coverage gating.

## Notes
- `assurance` runs Python assurance slices first and Node security tests second.
- Static linting is not part of this skill; use `build`.
- Commit message validation exists in CI, but it is not part of the canonical test runner.
