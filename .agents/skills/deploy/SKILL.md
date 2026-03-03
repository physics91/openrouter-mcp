---
name: deploy
description: Use when publishing or releasing the package to npm, or preparing a new version of openrouter-mcp for distribution.
---

# Deploy Skill

Target: npm registry (`@physics91/openrouter-mcp`). Always manual, intentional.

## Execution Baseline

- Prefer `python3` for Python commands.
- If `python3` is unavailable but `python` exists, use `python` as fallback.
- If pip installation is blocked by externally-managed environment (PEP 668), run quality/test gates in local `.venv`.

## Pre-flight Checklist

Run in order. Stop at first failure:

1. **Version**: Confirm `version` in `package.json` is the intended release (semver).
2. **Build gate**: Run `build` skill in check mode. `ruff`, `black`, and `isort` must all pass.
3. **Assurance gate**: `python3 run_tests.py assurance -v` must pass.
4. **npm auth**: `npm whoami` - if not logged in, run `npm login`.
5. **Manual confirmation**: Confirm with the user before publish.

## Publish

```
npm publish --access public
```

## Post-publish

1. Tag the release in git:
   ```
   git tag v<version>
   git push origin v<version>
   ```
2. Verify: `npm info @physics91/openrouter-mcp version`

## Package Contents

Defined by `files` field in `package.json`:
`bin/`, `src/`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `docs/`, `README.md`, `CONTRIBUTING.md`, `LICENSE`

## Notes
- No automated publish CI exists. This is always a deliberate manual action.
- The `prepublishOnly` script is a no-op; pre-flight checks above are the guard.
- The assurance gate's Node security test runs only after the pytest gate succeeds.
- Always confirm with the user before running `npm publish`.
