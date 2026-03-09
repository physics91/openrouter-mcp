# OpenRouter MCP Server

[![npm version](https://img.shields.io/npm/v/@physics91/openrouter-mcp?logo=npm)](https://www.npmjs.com/package/@physics91/openrouter-mcp)
[![repo version](https://img.shields.io/badge/dynamic/json?url=https://raw.githubusercontent.com/physics91/openrouter-mcp/develop/package.json&query=%24.version&label=repo%20version)](https://github.com/physics91/openrouter-mcp/blob/develop/package.json)
[![npm downloads](https://img.shields.io/npm/dw/@physics91/openrouter-mcp?logo=npm)](https://www.npmjs.com/package/@physics91/openrouter-mcp)
[![node](https://img.shields.io/node/v/@physics91/openrouter-mcp)](https://www.npmjs.com/package/@physics91/openrouter-mcp)
[![license](https://img.shields.io/npm/l/@physics91/openrouter-mcp)](LICENSE)
[![assurance required](https://github.com/physics91/openrouter-mcp/actions/workflows/assurance-required.yml/badge.svg?branch=develop)](https://github.com/physics91/openrouter-mcp/actions/workflows/assurance-required.yml?query=branch%3Adevelop)
[![last commit](https://img.shields.io/github/last-commit/physics91/openrouter-mcp)](https://github.com/physics91/openrouter-mcp/commits/develop)

A Model Context Protocol (MCP) server for OpenRouter. Register it in MCP-compatible clients that can launch a local stdio server to use OpenRouter models for chat, vision, benchmarking, and collective-intelligence workflows.

## Features
- MCP tools: chat, model listing, usage stats, vision chat, vision model listing, free chat, free model listing, free model metrics
- Benchmarking suite and performance comparison tools
- Collective intelligence tools (consensus, ensemble reasoning, adaptive routing, cross-model validation, collaborative solving)
- Secure API key storage (OS keychain, encrypted file, or .env) with audit logging
- Streaming responses, caching, and rich model metadata

## Quick start
```bash
npx @physics91/openrouter-mcp init
npx @physics91/openrouter-mcp start
```

Global install:
```bash
npm install -g @physics91/openrouter-mcp
openrouter-mcp init
openrouter-mcp start
```

## MCP client setup
Client config formats differ, but the launch information is usually the same:
- `command`: `npx`
- `args`: `["@physics91/openrouter-mcp", "start"]`
- `env`:
  Use only when the client cannot rely on `openrouter-mcp init` or inherited environment variables.

Recommended credential flow:
- Run `npx @physics91/openrouter-mcp init`
- Let `openrouter-mcp start` resolve the API key from secure storage or runtime environment

Client-specific examples:
- Claude Desktop: `mcpServers` in `claude_desktop_config.json`
- Claude Code: `claude mcp add ...` or project `.mcp.json`
- VS Code: `servers` in `.vscode/mcp.json`

See `docs/MCP_CLIENT_GUIDE.md` for the common flow and client-specific examples.

## Prerequisites
- Node.js 16+
- Python 3.10+ (`python` or `python3` must be available in `PATH`)
- First run attempts dependency install via `<python> -m pip install -r requirements.txt`
- OpenRouter API key: https://openrouter.ai

## DevOps Readiness (Clone -> Test/Build/Deploy)

If you clone this repository and want to trust local DevOps gates immediately, run this baseline once:

```bash
git clone <repo-url>
cd openrouter-mcp
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm install --no-audit --no-fund
```

Then run the quality/release gates:

1. Build gate (`build` skill):
```bash
ruff check src/ tests/
black --check src/ tests/
isort --check-only src/ tests/
```
2. Test gate (`test` skill):
```bash
python3 run_tests.py assurance -v
```
3. Deploy pre-flight (`deploy` skill):
```bash
npm whoami
```

Notes:
- `assurance` includes Python test gates and then `npm run test:security` only after pytest passes.
- If your OS blocks global pip installs (PEP 668), use `.venv` as shown above.
- `npm run build` is intentionally a no-op in this project; static quality gates above are the real build criteria.
- Publishing is always manual and intentional: `npm publish --access public` only after all gates pass and explicit confirmation.

## CLI
Use `openrouter-mcp <command>` or `npx @physics91/openrouter-mcp <command>`.

Commands:
- `start` Start the MCP server (stdio)
- `init` Initialize API key storage
- `status` Show configuration status
- `install-claude` Configure Claude Desktop
- `install-claude-code` Configure Claude Code CLI
- `rotate-key` Rotate API key across storage
- `delete-credentials` Remove stored credentials
- `security-audit` Audit credential storage and permissions
- `migrate-encryption` Migrate encrypted credentials to v2.0

Global options: `--verbose`, `--debug`
`start` options: `--host`, `--port`

## MCP client integration
- Common MCP client setup: `docs/MCP_CLIENT_GUIDE.md`
- Claude Desktop shortcut: `openrouter-mcp install-claude`
- Claude Code CLI shortcut: `openrouter-mcp install-claude-code`
- Generated server entries use: `npx @physics91/openrouter-mcp start`

See:
- `docs/MCP_CLIENT_GUIDE.md`
- `docs/CLAUDE_DESKTOP_GUIDE.md`
- `docs/CLAUDE_CODE_GUIDE.md`

## Notes
- Vision tools accept images as base64 or URL only (file paths are not supported).
- API keys should not be committed. Use `init` for secure storage. See `SECURITY.md`.

## Documentation
- `docs/INSTALLATION.md`
- `docs/MCP_CLIENT_GUIDE.md`
- `docs/CLAUDE_DESKTOP_GUIDE.md`
- `docs/CLAUDE_CODE_GUIDE.md`
- `docs/API.md`
- `docs/SECURITY.md`
- `docs/MULTIMODAL_GUIDE.md`
- `docs/BENCHMARK_GUIDE.md`
- `docs/SECURE_STORAGE_INTEGRATION.md`
- `docs/QUICK_REFERENCE.md`
- `docs/USAGE_GUIDE_KR.md`
- `docs/CLAUDE_CODE_SETUP_KR.md`

## Contributing
See `CONTRIBUTING.md`.

Quick setup for local hook enforcement:

```bash
pip install -r requirements-dev.txt
pre-commit install
```

The installed hooks enforce:
- `pre-commit` fast checks before commit
- `commit-msg` Conventional Commit format in English
- `pre-push` smoke tests

Deeper static analysis remains available as advisory/manual checks rather than push blockers.
Use `pre-commit run --hook-stage manual mypy-advisory --all-files` (and the other `*-advisory` hooks) when you want the broader reports locally.

## License
MIT
