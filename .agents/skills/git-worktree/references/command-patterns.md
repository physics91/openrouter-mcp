# Command Patterns

## Quick Checks
```bash
git worktree list --porcelain
git branch -vv
```

## Create Worktrees
Create new branch + new linked worktree:
```bash
git worktree add ../wt-<topic> -b <topic-branch> <start-point>
```

Use existing local branch:
```bash
git worktree add ../wt-<name> <existing-branch>
```

Detached worktree for one-off review/test:
```bash
git worktree add --detach ../wt-review <commit-ish>
```

Track remote branch when creating:
```bash
git worktree add --track -b <branch> ../wt-<name> origin/<branch>
```

## Worktree-Specific Setup
Delay checkout to customize first (for sparse setup):
```bash
git worktree add --no-checkout ../wt-<name> <branch-or-commit>
```

Enable/read per-worktree config:
```bash
git config extensions.worktreeConfig true
git config --worktree <key> <value>
```

Example sparse flow per worktree:
```bash
git -C ../wt-<name> sparse-checkout set <dir1> <dir2>
```

## Maintenance
Remove clean linked worktree:
```bash
git worktree remove ../wt-<name>
```

Force-remove unclean linked worktree:
```bash
git worktree remove --force ../wt-<name>
```

Prune stale admin entries:
```bash
git worktree prune --verbose
```

Lock/unlock portable or temporarily unavailable worktree:
```bash
git worktree lock --reason "portable device" ../wt-<name>
git worktree unlock ../wt-<name>
```

Repair metadata after manual move:
```bash
git worktree repair
# or specify moved paths when needed
git worktree repair <new-path-1> <new-path-2>
```

## Policy Defaults (Recommended)
```bash
# Keep default grace period or set explicit policy
git config gc.worktreePruneExpire 90.days.ago

# Optional: make link files resilient to directory moves
git config worktree.useRelativePaths true
```

## Script-Safe Path Resolution
```bash
git rev-parse --show-toplevel
git rev-parse --git-dir
git rev-parse --git-common-dir
git rev-parse --git-path HEAD
```

Do not hardcode `.git/worktrees/...` paths in automation.
