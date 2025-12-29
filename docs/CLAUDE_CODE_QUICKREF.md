# Claude Code MCP - Quick Reference

> 빠른 설정 및 사용 참조 가이드

## ⚡ 가장 빠른 설정 (3분)

### 방법 1: 설정 파일에 직접 (권장) ⭐

```bash
# 1. 설정 파일 생성
mkdir -p ~/.claude
nano ~/.claude/claude_code_config.json
```

**복사해서 붙여넣기**:
```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-your-actual-key"
      }
    }
  }
}
```

```bash
# 2. 파일 권한 설정
chmod 600 ~/.claude/claude_code_config.json

# 3. 테스트
claude "List available models"
```

**완료!** ✅

### 방법 2: 환경변수 (팀 공유 시) ⭐

```bash
# 1. 환경변수 설정
echo 'export OPENROUTER_API_KEY="sk-or-v1-your-key"' >> ~/.bashrc
source ~/.bashrc

# 2. 설정 파일 생성
cat > ~/.claude/claude_code_config.json << 'EOF'
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    }
  }
}
EOF

# 3. 테스트
claude "List available models"
```

---

## 📍 설정 파일 위치

| OS | 경로 |
|----|------|
| **macOS/Linux** | `~/.claude/claude_code_config.json` |
| **Windows** | `%USERPROFILE%\.claude\claude_code_config.json` |

---

## 📝 설정 템플릿 (복사해서 사용)

### 기본 설정 (가장 간단) ⭐

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-your-key-here"
      }
    }
  }
}
```

### 환경변수 참조 (팀 공유용) ⭐

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    }
  }
}
```

### 고급 설정

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start", "--port", "9000"],
      "env": {
        "LOG_LEVEL": "INFO",
        "CACHE_TTL_HOURS": "6",
        "OPENROUTER_VERBOSE_LOGGING": "false"
      }
    }
  }
}
```

---

## 🎯 자주 쓰는 명령어

### 설정 및 확인

```bash
# MCP 서버 목록
claude mcp list

# 툴 목록 확인
claude mcp tools openrouter

# 서버 재시작
claude mcp reload openrouter

# 설정 파일 위치 확인
claude config --show
```

### 기본 사용

```bash
# 모델 목록
claude "List all available AI models"

# 특정 모델 사용
claude "Use GPT-4 to explain quantum computing"
claude "Use Claude Opus to review my code"

# 이미지 분석
claude "Use GPT-4 Vision to analyze diagram.png"
```

### Collective Intelligence

```bash
# 다중 모델 합의
claude "Use consensus from 3 models to answer: AI의 미래는?"

# 복잡한 문제 해결
claude "Use ensemble reasoning to solve this problem"

# 교차 검증
claude "Use cross-model validation to verify this answer"
```

---

## 🔧 문제 해결 Quick Fix

### MCP 서버를 찾을 수 없음

```bash
npx openrouter-mcp install-claude-code
claude mcp list
```

### 서버 시작 실패

```bash
# 수동 시작으로 에러 확인
npx openrouter-mcp start --debug

# Python 확인
python --version  # 3.9+ 필요

# 포트 변경 (충돌 시)
# 설정 파일에서: "args": ["openrouter-mcp", "start", "--port", "9000"]
```

### API 키 인식 안 됨

```bash
# 재초기화
npx openrouter-mcp init

# 상태 확인
npx openrouter-mcp status

# 환경변수로 설정 (임시)
export OPENROUTER_API_KEY="sk-or-v1-..."
```

### Tools 목록 비어있음

```bash
# 서버 재시작
npx openrouter-mcp start --debug

# MCP 재로드
claude mcp reload openrouter

# 로그 확인
tail -f ~/.openrouter-mcp/logs/server.log
```

---

## 💡 유용한 Alias

**`.bashrc` 또는 `.zshrc`에 추가**:

```bash
# 단축 명령어
alias cc="claude"
alias cc-gpt4="claude 'Use GPT-4 to'"
alias cc-opus="claude 'Use Claude Opus to'"
alias cc-models="claude 'List all available models'"

# 사용 예시
cc-gpt4 "explain this algorithm"
cc-opus "review this code"
cc-models
```

---

## 📊 검증 체크리스트

설정 후 확인:

```bash
# 1. 설정 파일 존재
ls ~/.claude/claude_code_config.json

# 2. JSON 문법 검증
cat ~/.claude/claude_code_config.json | python -m json.tool

# 3. MCP 서버 등록
claude mcp list

# 4. Tools 로드
claude mcp tools openrouter

# 5. 간단한 테스트
claude "List available models"

# 6. API 키 확인
npx openrouter-mcp status
```

**모두 ✓ 표시되면 설정 완료!**

---

## 🎯 환경별 권장 설정

### 개발 환경

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start", "--debug"],
      "env": {
        "LOG_LEVEL": "DEBUG",
        "OPENROUTER_VERBOSE_LOGGING": "true"
      }
    }
  }
}
```

### 프로덕션 환경

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "LOG_LEVEL": "WARNING",
        "CACHE_TTL_HOURS": "6"
      }
    }
  }
}
```

---

## 🔒 보안 Best Practices

✅ **권장**:
- OS Keychain 사용
- 설정 파일 권한: `chmod 600 ~/.claude/claude_code_config.json`
- 환경변수 활용
- 정기적인 키 로테이션

❌ **피해야 할 것**:
- 설정 파일에 API 키 직접 저장
- Git에 설정 파일 커밋
- Verbose 로깅 프로덕션 사용
- 설정 파일 공유

---

## 📚 더 알아보기

- **상세 가이드**: `CLAUDE_CODE_SETUP_KR.md`
- **전체 사용법**: `USAGE_GUIDE_KR.md`
- **빠른 시작**: `QUICKSTART.md`

---

**마지막 업데이트**: 2025-11-18
