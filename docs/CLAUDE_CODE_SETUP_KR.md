# Claude Code MCP 설정 가이드

Claude Code에서 OpenRouter MCP를 붙이는 최신 권장 흐름은 `claude mcp add` 또는 프로젝트 `.mcp.json`을 사용하는 방식입니다.

## 권장 설정

1. API 키를 한 번 안전하게 저장합니다.

```bash
npx @physics91/openrouter-mcp@latest init
```

2. Claude Code 사용자 범위에 MCP 서버를 등록합니다.

```bash
claude mcp add --transport stdio --scope user openrouter -- npx @physics91/openrouter-mcp start
```

3. 등록 상태를 확인합니다.

```bash
claude mcp list
claude mcp get openrouter
```

이 방식에서는 Claude Code 설정에 API 키를 직접 넣지 않아도 됩니다. 실제 실행 시 `openrouter-mcp start`가 secure storage 또는 환경변수에서 키를 읽습니다.

## 프로젝트 범위 설정

저장소에 함께 두고 싶다면 프로젝트 루트에 `.mcp.json`을 만드세요.

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

현재 Claude Code 기준:
- 사용자 범위 MCP 서버: `~/.claude.json`
- 프로젝트 범위 MCP 서버: `.mcp.json`

## 대안

### Claude Desktop에서 가져오기

이미 Claude Desktop에 등록돼 있다면:

```bash
claude mcp add-from-claude-desktop
```

확인:

```bash
claude mcp list
```

### 패키지 단축 명령

이 패키지는 아래 명령도 제공합니다.

```bash
npx @physics91/openrouter-mcp@latest install-claude-code
```

다만 최신 Claude Code 네이티브 흐름 기준으로는 `claude mcp add ...` 또는 `.mcp.json` 방식을 우선 권장합니다.

## 사용 예시

```bash
claude "List available AI models using OpenRouter"
claude "Show my OpenRouter usage for today"
claude "Compare GPT-4 and Claude Opus using OpenRouter tools"
```

## 문제 해결

### 서버가 안 보일 때

```bash
claude mcp list
claude mcp get openrouter
```

없다면 다시 등록합니다.

```bash
claude mcp add --transport stdio --scope user openrouter -- npx @physics91/openrouter-mcp start
```

### 인증 문제가 있을 때

- `npx @physics91/openrouter-mcp@latest init` 재실행
- 또는 Claude Code를 실행하는 셸에 `OPENROUTER_API_KEY` 설정
- `npx @physics91/openrouter-mcp@latest status`로 상태 확인

## 함께 볼 문서

- `MCP_CLIENT_GUIDE.md`
- `INSTALLATION.md`
- `CLAUDE_CODE_GUIDE.md`
- `SECURITY.md`
