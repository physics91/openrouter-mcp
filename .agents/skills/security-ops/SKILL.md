---
name: security-ops
description: Use when handling API key setup, credential rotation or deletion, security-audit runs, shared-environment risk checks, or security-document hygiene in openrouter-mcp
---

# Security Ops

## Overview

Use this skill for repository-local security operations around OpenRouter credentials and security hygiene.
It standardizes safe defaults, audit commands, and documentation checks before someone changes key storage or claims the setup is secure.

## Safe Defaults

- Prefer OS keychain over plaintext or ad hoc env-file storage.
- Treat shared shells, shared machines, CI logs, and screen sharing as elevated risk.
- Never paste real API keys into issues, docs, fixtures, or examples.
- Re-run a security audit after setup, rotation, or deletion changes.

## Repository Touchpoints

- `bin/secure-credentials.js`
- `bin/openrouter-mcp.js`
- `docs/SECURITY.md`
- `docs/SECURITY_BEST_PRACTICES.md`
- `docs/SECURITY_QUICKSTART.md`
- `README.md`

## Standard Runbook

1. Inspect the current state:
   ```
   node bin/openrouter-mcp.js status
   node bin/openrouter-mcp.js security-audit
   ```
2. For first-time setup, run:
   ```
   node bin/openrouter-mcp.js init
   ```
3. For key rotation, run:
   ```
   node bin/openrouter-mcp.js rotate-key
   ```
4. For credential removal, run:
   ```
   node bin/openrouter-mcp.js delete-credentials
   ```
5. Re-run:
   ```
   node bin/openrouter-mcp.js security-audit
   ```
6. If docs changed, scan for placeholders and unsafe examples before closing the task.

## Documentation Hygiene

Run this when security docs or release docs were touched:

```
rg -n "yourproject.com|your-domain-here|security@" SECURITY.md docs/SECURITY.md docs/SECURITY_BEST_PRACTICES.md docs/SECURITY_QUICKSTART.md
```

If the repository still contains placeholder security contacts, call that out explicitly.

## Shared-Environment Warnings

- On a shared workstation, prefer keychain-backed storage and avoid `.env` unless the user explicitly accepts the risk.
- Before enabling verbose logging, check whether prompts or responses could expose secrets.
- If a task involves CI or automation, verify whether credentials are expected to live in env vars, encrypted files, or user-level stores.

## Done Definition

- The relevant credential action completed.
- `security-audit` was run after the change.
- Any placeholder or documentation risk was surfaced.
- No secret material was copied into repository files or logs.
