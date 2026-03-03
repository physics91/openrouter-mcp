---
name: build
description: Use when checking code quality, running linting, formatting code, or verifying static analysis gates before PR or publish.
---

# Build Skill

No compilation step exists. "Build" means passing all static quality gates.

## Execution Baseline

- Prefer `python3` when invoking Python modules or pip.
- If `python3` is unavailable but `python` exists, use `python` as fallback.

## Check Mode (CI-equivalent, read-only)

Run all three in order. All must exit 0:

```
ruff check src/ tests/
black --check src/ tests/
isort --check-only src/ tests/
```

If command executables are not on `PATH`, run module form:
```
python3 -m ruff check src/ tests/
python3 -m black --check src/ tests/
python3 -m isort --check-only src/ tests/
```

## Fix Mode (auto-correct)

```
ruff check src/ tests/ --fix
black src/ tests/
isort src/ tests/
```

Re-run check mode after fixing to confirm clean state.

## Optional: Type Checking

```
mypy src/
```

Not CI-required but recommended for new code.

## Dependency Check

If tools are missing:
```
python3 -m pip install -r requirements-dev.txt
```

## Notes
- `npm run build` is intentionally a no-op in this project, so it is not a quality gate.
- After auto-fixing, stage only changed files; do not `git add .`.
- Run the `test` skill after build passes to confirm nothing broke.
