---
name: git-worktree
description: Use when the user asks to continue with additional tasks while keeping current work in progress, or needs parallel branch development, hotfix interruption handling, and review sandboxes without extra clones. Use when tasks involve `git worktree add/list/remove/prune/lock/repair`, resolving branch-in-use conflicts across worktrees, configuring per-worktree settings (`git config --worktree`, `extensions.worktreeConfig`), or writing scripts that must resolve worktree paths safely with `git rev-parse`.
---

# Git Worktree

## Overview
Use this skill to operate multiple branches from one repository safely.
Default to safe workflows first, then use force/override options only for recovery.

## Additional Task Policy
If new tasks are added while current changes are still active, default to creating a new linked worktree instead of switching the current working directory.
Use branch switching in the same directory only when the user explicitly requests single-worktree mode.

## Workflow Decision
1. Need a new parallel branch workspace: use `git worktree add` with `-b`.
2. Need to work on an existing branch in another directory: use `git worktree add <path> <branch>`.
3. Need temporary checkout not tied to a branch (review/test): use detached mode.
4. Need to clean up or recover broken metadata: use `remove`, `prune`, `repair`, `lock` runbook.

For exact commands, read [command-patterns.md](./references/command-patterns.md).

## Safety Rules
- Treat `one active branch = one active worktree` as the default rule.
- Do not use `--ignore-other-worktrees` unless there is a clear recovery need.
- Do not delete worktree directories manually if `git worktree remove` is possible.
- When the worktree path is on removable/network storage, lock it.
- For scripts, never assume `.git` layout; resolve paths via `git rev-parse`.

## Standard Runbook
1. Create: add worktree with explicit branch/start-point.
2. Verify: check `git worktree list --porcelain` and branch linkage.
3. Work: commit/push from the linked directory.
4. Close: remove linked worktree with `git worktree remove`.
5. Maintenance: prune stale metadata and review prune policy.

## Recovery Runbook
1. Branch already checked out elsewhere:
   - Find owner worktree.
   - Prefer switching to that directory or creating a new branch.
   - Use override flags only if policy allows it.
2. Worktree path moved/deleted manually:
   - Run `git worktree repair` and `git worktree prune`.
3. Locked/prunable confusion:
   - Inspect lock status and reason, then unlock intentionally.

For concrete failure signatures and fixes, read [troubleshooting.md](./references/troubleshooting.md).

## Configuration Guidance
- Use per-worktree config when settings should differ by worktree.
- Keep shared repo defaults in common config; place worktree-specific settings in worktree config.
- If sparse-checkout differs by worktree, use worktree-specific sparse settings.

## References
- Command matrix: [command-patterns.md](./references/command-patterns.md)
- Failure handling: [troubleshooting.md](./references/troubleshooting.md)
- Research basis: `/docs/reports/git-worktree-skill-research-20260303.md`
