# Claude Code MCP Integration Guide

This guide covers the current Claude Code-native way to register OpenRouter MCP Server.

## Recommended Setup

1. Store the API key once:

```bash
npx @physics91/openrouter-mcp@latest init
```

2. Register the server in Claude Code user scope:

```bash
claude mcp add --transport stdio --scope user openrouter -- npx @physics91/openrouter-mcp start
```

3. Verify the registration:

```bash
claude mcp list
claude mcp get openrouter
```

`openrouter-mcp start` resolves credentials from secure storage or the environment at runtime, so the Claude Code MCP entry does not need to inline `OPENROUTER_API_KEY`.

## Project-Scoped Setup

If you want the server to live with the repository, create `.mcp.json` in the project root:

```json
{
  "mcpServers": {
    "openrouter": {
      "type": "stdio",
      "command": "npx",
      "args": ["@physics91/openrouter-mcp", "start"]
    }
  }
}
```

Claude Code stores:
- User-scoped MCP servers in `~/.claude.json`
- Project-scoped MCP servers in `.mcp.json`

## Alternative Paths

### Import from Claude Desktop

If OpenRouter is already configured in Claude Desktop:

```bash
claude mcp add-from-claude-desktop
```

Then confirm with:

```bash
claude mcp list
```

### Package Shortcut

This package still ships:

```bash
npx @physics91/openrouter-mcp@latest install-claude-code
```

Treat it as a package-managed convenience helper. For current Claude Code workflows, prefer `claude mcp add ...` or `.mcp.json`.

## Usage

Once registered, you can ask Claude Code to use the OpenRouter-backed tools naturally, for example:

```bash
claude "List available AI models using OpenRouter"
claude "Show my OpenRouter usage for today"
claude "Compare GPT-4 and Claude Opus using OpenRouter tools"
```

## Troubleshooting

### Server not showing up

```bash
claude mcp list
claude mcp get openrouter
```

If the server is missing, add it again:

```bash
claude mcp add --transport stdio --scope user openrouter -- npx @physics91/openrouter-mcp start
```

### Authentication issues

- Re-run `npx @physics91/openrouter-mcp@latest init`
- Or export `OPENROUTER_API_KEY` before launching Claude Code
- Confirm package status with `npx @physics91/openrouter-mcp@latest status`

## Related Docs

- `MCP_CLIENT_GUIDE.md`
- `INSTALLATION.md`
- `CLAUDE_CODE_SETUP_KR.md`
- `SECURITY.md`
