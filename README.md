# OpenRouter MCP Server

A Model Context Protocol (MCP) server for OpenRouter. Use OpenRouter models from MCP clients (Claude Desktop, Claude Code, etc.) with chat, vision, benchmarking, and collective-intelligence tools.

## Features
- MCP tools: chat, model listing, usage stats, vision chat, vision model listing
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

## Prerequisites
- Node.js 16+
- Python 3.9+ (dependencies auto-installed on first run)
- OpenRouter API key: https://openrouter.ai

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

Common options: `--verbose`, `--debug`, `--host`, `--port`.

## Integrations
- Claude Desktop: `openrouter-mcp install-claude`
- Claude Code CLI: `openrouter-mcp install-claude-code`

See:
- `docs/CLAUDE_DESKTOP_GUIDE.md`
- `docs/CLAUDE_CODE_GUIDE.md`

## Notes
- Vision tools accept images as base64 or URL only (file paths are not supported).
- API keys should not be committed. Use `init` for secure storage. See `SECURITY.md`.

## Documentation
- `docs/INDEX.md`
- `docs/INSTALLATION.md`
- `docs/API.md`
- `docs/MULTIMODAL_GUIDE.md`
- `docs/BENCHMARK_GUIDE.md`
- `docs/SECURE_STORAGE_INTEGRATION.md`
- `docs/QUICK_REFERENCE.md`

## Contributing
See `CONTRIBUTING.md`.

## License
MIT
