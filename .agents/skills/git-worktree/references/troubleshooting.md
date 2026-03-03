# Troubleshooting

## `... is already checked out at ...`
Cause: The target branch/ref is already held by another worktree.

Preferred fixes:
1. Work in the owning worktree directory.
2. Create a different branch for the new worktree.
3. Only if policy permits, use override flags (`--ignore-other-worktrees` / force variants).

Inspection commands:
```bash
git worktree list --porcelain
git branch -vv
```

## `git worktree remove` refuses (unclean worktree)
Cause: Tracked modifications and/or untracked files exist.

Fix options:
1. Commit/stash/clean intentionally, then remove.
2. If discard is intentional, force-remove:
```bash
git worktree remove --force <path>
```

## Stale `prunable` entries after manual deletion
Cause: Directory was deleted without `git worktree remove`.

Fix:
```bash
git worktree prune --verbose
```

Related policy key:
```bash
git config gc.worktreePruneExpire <duration|now|never>
```

## Main or linked worktree moved manually
Cause: Link metadata (`gitdir` relationship) no longer matches actual path.

Fix:
```bash
git worktree repair
# optionally specify moved paths
git worktree repair <new-path>
```

## Portable/network-mounted worktree gets pruned unexpectedly
Cause: Worktree not locked while path is intermittently unavailable.

Fix:
```bash
git worktree lock --reason "portable or network path" <path>
# later when stable:
git worktree unlock <path>
```

## Script fails because path assumptions break in linked worktrees
Cause: Script assumes a fixed `.git` layout.

Fix: use `rev-parse` outputs instead of string concatenation.
```bash
git rev-parse --git-dir
git rev-parse --git-common-dir
git rev-parse --git-path <name>
```
