---
name: release
description: >
  Create git tag, GitHub Release, and post-publish verification for openrouter-mcp after npm publish completes.
  Use after `deploy` skill has published to npm and you need to tag and create a GitHub Release.
  For building use `build`; for testing use `test`; for deployment and npm publish use `deploy`; for version bumping use `version`.
---

# Release

Target: git tags + GitHub Releases for `@physics91/openrouter-mcp`.

npm publish is handled by the `deploy` skill. This skill runs **after** a successful publish.

## Execution Baseline

- This skill assumes `deploy` has already published to npm successfully.
- If publish has not been done, delegate to `deploy` skill first.
- Release is always a deliberate manual action — never auto-triggered.

## Procedure

### 1. Pre-release Verification

Confirm these are true before proceeding:

```bash
VERSION=$(node -p "require('./package.json').version")

# Verify npm publish already happened (fail fast on network/auth errors)
if ! PUBLISHED=$(npm info @physics91/openrouter-mcp version 2>/dev/null); then
  echo "Failed to query npm registry; fix auth/network first"; exit 1
fi
echo "package.json: ${VERSION}, npm: ${PUBLISHED}"
if [ "$VERSION" != "$PUBLISHED" ]; then
  echo "npm registry version ($PUBLISHED) does not match package.json ($VERSION); run deploy first"
  exit 1
fi

# CHANGELOG.md must have an entry for this version
grep -q "^## \[${VERSION}\]" CHANGELOG.md || { echo "CHANGELOG.md is missing entry for ${VERSION}"; exit 1; }

# Working tree must be clean
if [ -n "$(git status --short)" ]; then
  echo "Working tree is dirty — commit or stash first"; exit 1
fi

# Must be on main or develop
BRANCH=$(git branch --show-current)
case "$BRANCH" in
  main|develop|release/*|hotfix/*) ;;
  *) echo "Release only from main, develop, release/*, or hotfix/* (current: $BRANCH)"; exit 1 ;;
esac
```

- If npm version does not match package.json version, run `deploy` first.

### 2. Tag the Release

```bash
VERSION=$(node -p "require('./package.json').version")
git tag -a "v${VERSION}" -m "Release v${VERSION}"
```

- Use annotated tags (`-a`), not lightweight tags.
- Tag message should be `Release v<version>`.
- If the tag already exists, stop and confirm with the user.

### 3. Push Tag

```bash
VERSION=$(node -p "require('./package.json').version")
git push origin "v${VERSION}"
```

### 4. Create GitHub Release

```bash
VERSION=$(node -p "require('./package.json').version")

# Extract changelog section for this version (index match avoids regex pitfalls with dots)
awk -v ver="${VERSION}" '/^## \[/{if(flag)exit; if(index($0,"["ver"]"))flag=1; next} flag' CHANGELOG.md > /tmp/release-notes.md

# Verify remote tag exists before creating release
git ls-remote --exit-code --tags origin "refs/tags/v${VERSION}" >/dev/null

if command -v gh >/dev/null 2>&1; then
  gh release create "v${VERSION}" \
    --verify-tag \
    --title "v${VERSION}" \
    --notes-file /tmp/release-notes.md
else
  echo "gh CLI not found. Create release manually:"
  echo "  https://github.com/physics91/openrouter-mcp/releases/new?tag=v${VERSION}"
fi
```

- Release title: `v<version>`
- Release body: extracted from CHANGELOG.md for this version.

### 5. Post-release Verification

```bash
VERSION=$(node -p "require('./package.json').version")

# Verify npm registry
npm info @physics91/openrouter-mcp version

# Verify GitHub release
if command -v gh >/dev/null 2>&1; then
  gh release view "v${VERSION}"
else
  echo "Verify manually: https://github.com/physics91/openrouter-mcp/releases/tag/v${VERSION}"
fi

# Verify git tag
git tag -l "v${VERSION}"
```

### 6. Post-release Housekeeping

- If released from `main`, consider merging back to `develop` if needed.
- Update any open issues/PRs that reference the released version.

## npm Provenance (Future)

npm supports publish provenance via `--provenance` flag with GitHub Actions OIDC.
Currently this project publishes manually, so provenance is not configured.
When a publish workflow is added to CI, enable `--provenance` for supply chain security.

## Caveats

- No automated publish CI workflow exists. Release is always manual.
- `prepublishOnly` in package.json is a no-op — rely on `deploy` pre-flight.
- CHANGELOG.md comparison links reference GitHub compare URLs — verify they resolve.
- If releasing a version that was already tagged (e.g., re-release), delete the old tag first with user confirmation.
