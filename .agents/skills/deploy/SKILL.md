---
name: deploy
description: Use when publishing or releasing openrouter-mcp to npm, or preparing a version for distribution with metadata and release checks
---

# Deploy Skill

Target: npm registry (`@physics91/openrouter-mcp`). Always manual, intentional.

## Execution Baseline

- Prefer `python3` for Python commands.
- If `python3` is unavailable but `python` exists, use `python` as fallback.
- If pip installation is blocked by externally-managed environment (PEP 668), run quality/test gates in local `.venv`.
- `deploy` owns release hygiene as well as publish commands. Do not treat metadata checks as optional.

## Pre-flight Checklist

Run in order. Stop at first failure:

1. **Clean tree**: Working tree must be clean (`git status --short` returns empty). Dirty state means the publish artifact may not match the tagged commit.
2. **Branch**: Must be on `main`, `develop`, `release/*`, or `hotfix/*`.
3. **Version**: Confirm `version` in `package.json` is the intended release (semver).
4. **Build gate**: Run `build` skill in check mode. `ruff`, `black`, and `isort` must all pass.
5. **Assurance gate**: Run `python3 run_tests.py assurance -v` through the `test` skill.
6. **Metadata sanity**: Check `package.json` fields:
   - `author`
   - `homepage`
   - `repository`
   - `bugs`
7. **Placeholder scan**: Run:
   ```
   rg -n "yourusername|yourproject.com|your-domain-here|Your Name" package.json CHANGELOG.md README.md SECURITY.md docs
   ```
   Release only when the results are understood and intentional.
8. **Release notes and links**: Verify `CHANGELOG.md` version section and comparison links.
9. **Package contents**: Run:
   ```
   npm pack --dry-run
   ```
   Confirm the package includes the expected files and excludes junk.
10. **Install-doc consistency**: Spot-check scoped package naming in `README.md` and `docs/INSTALLATION.md`.
11. **npm auth**: Run `npm whoami`. If not logged in, run `npm login`.
12. **Manual confirmation**: Confirm with the user before publish.

## Publish

```
npm publish --access public
```

## Post-publish

1. Tag and create GitHub Release: delegate to `release` skill.
2. Verify registry version:
   ```
   npm info @physics91/openrouter-mcp version
   ```
3. If the package page or docs are part of the release checklist, verify them after publish.

## Package Contents

Defined by `files` field in `package.json`:
`bin/`, `src/`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `docs/`, `README.md`, `CONTRIBUTING.md`, `LICENSE`

## Notes
- No automated publish CI exists. This is always a deliberate manual action.
- The `prepublishOnly` script is a no-op; pre-flight checks above are the guard.
- The assurance gate's Node security test runs only after the pytest gate succeeds.
- Always confirm with the user before running `npm publish`.
- npm docs recommend proper package metadata and support trusted publishing/provenance; keep the skill ready for that transition even if the current release flow is manual.
