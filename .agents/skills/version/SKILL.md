---
name: version
description: >
  Bump the package version, update CHANGELOG.md, and prepare the repository for release.
  Use when incrementing the version number for a new release cycle.
  For building use `build`; for testing use `test`; for deployment preparation use `deploy`; for publishing releases use `release`.
---

# Version

Manages semver version bumps and changelog updates for `@physics91/openrouter-mcp`.

## Execution Baseline

- This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
- Changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.
- Version bumps are manual and intentional — no automated semver tool is configured.
- Always confirm the bump type (major/minor/patch) with the user.

## Procedure

### 1. Determine Bump Type

Analyze changes since the last release to recommend a bump type:

```bash
# Show last tagged version
git describe --tags --abbrev=0 2>/dev/null || echo "no tags"

# Show commits since last tag
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)
if [ -n "$LAST_TAG" ]; then
  git log --oneline "${LAST_TAG}..HEAD"
else
  git log --oneline -20
fi
```

Apply semver rules:
- **MAJOR**: Breaking changes to public API (MCP tool interface, CLI commands, config format)
- **MINOR**: New features, new MCP tools, new CLI commands (backward-compatible)
- **PATCH**: Bug fixes, performance improvements, documentation updates

Present recommendation to user and confirm.

### 2. Bump package.json Version

```bash
# Use npm version without git tag (tagging is handled by release skill)
npm version <major|minor|patch> --no-git-tag-version
```

This updates `version` in `package.json` (and `package-lock.json` if present).

### 3. Update CHANGELOG.md

Add a new version section following Keep a Changelog format:

```markdown
## [<new-version>] - <YYYY-MM-DD>

### Added
- ...

### Changed
- ...

### Fixed
- ...
```

Rules:
- Date format: `YYYY-MM-DD` (ISO 8601).
- Categories: Added, Changed, Deprecated, Removed, Fixed, Security.
- Only include categories that have entries.
- Write entries from git log analysis — summarize by impact, not by commit.

### 4. Update Comparison Links

At the bottom of CHANGELOG.md, add/update the comparison link:

```markdown
[<new-version>]: https://github.com/physics91/openrouter-mcp/compare/v<prev-version>...v<new-version>
```

### 5. Verify Changes

```bash
# Review the diff
git diff package.json CHANGELOG.md

# Confirm version
node -p "require('./package.json').version"
```

### 6. Commit Version Bump

Use `commit-work` skill to commit. Suggested message format:

```
chore(version): bump to v<new-version>
```

Do not tag here — tagging is handled by the `release` skill.

## Best Practices

- Bump version on the branch where the release will be cut (usually `main` or a release branch).
- Keep CHANGELOG.md entries human-readable — avoid copy-pasting raw commit messages.
- When deprecating features, note them in CHANGELOG under `Deprecated` for at least one minor release before removal.
- Review the comparison link to ensure it will resolve on GitHub after pushing.

## Caveats

- No automated changelog generation tool is configured.
- CHANGELOG.md is manually maintained — ensure it stays in sync with actual changes.
- `npm version` without `--no-git-tag-version` will auto-create a git tag, which conflicts with the `release` skill's tagging flow. Always use `--no-git-tag-version`.
- Current state: package.json says v1.4.0 but only v1.3.1 tag exists — there's a gap in version/tag history.
- `package-lock.json` is not currently tracked in git; `npm version` may still create or modify it locally, so review it explicitly before committing.
