---
name: test
description: Use when running tests, checking test results, verifying coverage, or validating PR readiness for the openrouter-mcp project.
---

# Test Skill

## Execution Baseline

- Prefer `python3` for running `run_tests.py` and installing Python dependencies.
- If `python3` is unavailable but `python` exists, use `python` as fallback.

## Running Tests
1. If the user does not specify a suite, ask which suite to run. Default recommendation: `assurance` for PR readiness.
2. Run the canonical test runner:
   ```
   python3 run_tests.py <suite> -v
   ```
3. If `pytest-cov` is missing (assurance/coverage fails), install first:
   ```
   python3 -m pip install -r requirements-dev.txt
   ```
4. Report pass/fail outcome. Surface failing test names or coverage shortfall.

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

### Flags

- `-v`: Always include for readable output.
- `--no-cov`: Use only for debugging when speed is more important than coverage gating.

## Notes
- The `assurance` suite also runs `npm run test:security` (Node.js) and requires `npm`.
- If `node_modules/` is missing, `run_tests.py` may run `npm install --no-audit --no-fund` automatically.
- For `real` suite, `OPENROUTER_API_KEY` must be set. This is interactive (prompts y/N).
- Static linting is NOT part of this skill - use the `build` skill.
