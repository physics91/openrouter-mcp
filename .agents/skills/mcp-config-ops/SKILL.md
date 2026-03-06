---
name: mcp-config-ops
description: Use when installing or repairing Claude Desktop or Claude Code MCP config, checking status, backing up config files, or fixing config drift in openrouter-mcp
---

# Mcp Config Ops

## Overview

Use this skill when a task touches MCP client configuration rather than core model behavior.
It standardizes status checks, backup discipline, installer flows, and config-drift troubleshooting for the repository's Node-to-Python bootstrap path.

## Repository Touchpoints

- `bin/openrouter-mcp.js`
- `src/openrouter_mcp/cli/mcp_manager.py`
- `src/openrouter_mcp/cli/commands.py`
- `src/openrouter_mcp/server.py`
- `docs/CLAUDE_DESKTOP_GUIDE.md`
- `docs/CLAUDE_CODE_GUIDE.md`
- `docs/INSTALLATION.md`

## Standard Workflow

1. Inspect the current state:
   ```
   node bin/openrouter-mcp.js status
   ```
2. Identify the target client:
   - Claude Desktop
   - Claude Code
   - both
3. Back up any config file before mutation.
4. Apply one installer or repair action at a time:
   ```
   node bin/openrouter-mcp.js install-claude
   node bin/openrouter-mcp.js install-claude-code
   ```
5. Re-run `status` and inspect the written config path.
6. If documentation changed, verify that package names and command examples still match the actual CLI path.

## Backup And Restore Rules

- Never overwrite a user config file without first capturing a backup path.
- If the installer already creates backups, record where they are.
- If an install or migration goes wrong, restore the backup before trying a second fix path.

## Consistency Checks

- Check command examples against the actual package scope:
  ```
  rg -n "@physics91/openrouter-mcp|openrouter-mcp" README.md docs
  ```
- Watch for drift between install docs and actual CLI behavior.
- Treat Node/Python bootstrap issues as part of config operations when they block installation or status checks.

## Recovery Pattern

If config drift or install failure is reported:

1. Capture the failing path and command.
2. Compare generated config with the documented expected shape.
3. Restore backup if the generated output is clearly wrong.
4. Re-run a single installer path.
5. Finish by running `status` again.

## Done Definition

- The target integration was inspected or updated intentionally.
- Backup or restore handling was explicit.
- The final `status` output was reviewed.
- Any package-name or doc-command mismatch was surfaced.
