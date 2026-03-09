# MCP Client Integration Guide

This guide explains the common registration pattern for OpenRouter MCP Server across MCP clients. The exact file format is client-specific, so treat `command`, `args`, and credential flow as the portable part of the setup, then apply the right client wrapper around it.

## Common Server Launch Information

Most local stdio MCP clients need these values:

```json
{
  "command": "npx",
  "args": ["@physics91/openrouter-mcp", "start"]
}
```

If the client cannot resolve `npx`, install the package globally and use:

```json
{
  "command": "openrouter-mcp",
  "args": ["start"]
}
```

## Credential Flow

### Preferred

```bash
npx @physics91/openrouter-mcp@latest init
```

Then let `openrouter-mcp start` resolve the API key from secure storage or the current environment when the client launches the server.

### Fallback

If your client requires inline environment variables, add:

```json
{
  "env": {
    "OPENROUTER_API_KEY": "sk-or-v1-...",
    "OPENROUTER_APP_NAME": "my-mcp-client",
    "OPENROUTER_HTTP_REFERER": "https://example.com"
  }
}
```

Avoid committing config files that contain plaintext API keys.

## Client Examples

### Claude Desktop

Claude Desktop uses `mcpServers` in `claude_desktop_config.json`.

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["@physics91/openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-..."
      }
    }
  }
}
```

Notes:
- The official local-server flow is documented for macOS and Windows.
- The project shortcut `npx @physics91/openrouter-mcp@latest install-claude` writes this entry automatically.
- Claude Desktop currently requires the API key to be present in the config for this path.

### Claude Code

Claude Code has its own native MCP workflow. Recommended options:

1. Native CLI registration

```bash
npx @physics91/openrouter-mcp@latest init
claude mcp add --transport stdio --scope user openrouter -- npx @physics91/openrouter-mcp start
```

2. Project-scoped `.mcp.json`

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

Notes:
- User-scoped MCP servers are stored in `~/.claude.json`.
- Project-scoped MCP servers are stored in `.mcp.json`.
- `claude mcp add-from-claude-desktop` can import supported Claude Desktop entries.
- This package still ships `install-claude-code`, but the Claude Code-native workflow above is the current recommended path.

### VS Code

VS Code stores MCP config in `mcp.json`, usually `.vscode/mcp.json` for a workspace. Its root key is `servers`, not `mcpServers`.

```json
{
  "servers": {
    "openrouter": {
      "type": "stdio",
      "command": "npx",
      "args": ["@physics91/openrouter-mcp", "start"]
    }
  }
}
```

## Verification

Local package status:

```bash
npx @physics91/openrouter-mcp@latest status
```

Client-side checks:
- Confirm the `openrouter` server appears in the client MCP list
- Ask the client to list tools or available models
- Run a simple request such as `List available AI models using OpenRouter`

## Related Guides

- `CLAUDE_DESKTOP_GUIDE.md`
- `CLAUDE_CODE_GUIDE.md`
- `INSTALLATION.md`
- `SECURITY.md`
