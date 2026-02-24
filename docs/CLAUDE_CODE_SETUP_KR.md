# Claude Code MCP 설정 가이드

> Claude Code CLI에서 OpenRouter MCP를 사용하는 완벽 가이드

## 📋 목차

1. [자동 설정 (권장)](#자동-설정-권장)
2. [수동 설정](#수동-설정)
3. [설정 확인](#설정-확인)
4. [사용 예시](#사용-예시)
5. [고급 설정](#고급-설정)
6. [문제 해결](#문제-해결)

---

## 🚀 빠른 설정 (권장)

### 방법 1: 설정 파일에 직접 (가장 간편) ⭐

```bash
# 1. 설정 파일 생성
mkdir -p ~/.claude

# 2. 설정 파일 편집
nano ~/.claude/claude_code_config.json
# (Windows: notepad %USERPROFILE%\.claude\claude_code_config.json)
```

**설정 내용 (복사해서 붙여넣기)**:
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

**3. API 키 교체**:
- `sk-or-v1-your-key-here`를 실제 OpenRouter API 키로 변경

**4. 파일 권한 설정** (중요):
```bash
chmod 600 ~/.claude/claude_code_config.json
```

**장점**:
- ✅ 가장 간단하고 명확
- ✅ 한 곳에 모든 설정
- ✅ 디버깅 쉬움
- ✅ 즉시 작동

**보안 주의**:
- ⚠️ Git에 커밋하지 말 것
- ⚠️ 파일 권한 제한 필수

### 방법 2: 환경변수 참조 (팀 공유 시) ⭐

**1. 환경변수 설정**:
```bash
# .bashrc 또는 .zshrc에 추가
export OPENROUTER_API_KEY="sk-or-v1-your-actual-key"

# 적용
source ~/.bashrc
```

**2. 설정 파일**:
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

**장점**:
- ✅ 설정 파일을 Git에 안전하게 공유 가능
- ✅ 여러 도구에서 같은 키 사용
- ✅ 팀원마다 다른 키 사용 가능

### 방법 3: 자동 설치 명령어

```bash
npx openrouter-mcp install-claude-code
```

**주의**: 이 명령어는 기본 설정만 생성합니다. API 키는 별도로 설정해야 합니다.

### 3단계: 설정 확인

```bash
# Claude Code 버전 확인
claude --version

# MCP 서버 상태 확인
claude mcp list
```

**출력 예시**:
```
Available MCP servers:
- openrouter (running)
  Tools: 15
  Status: ✓ Connected
```

---

## 🔧 수동 설정

자동 설정이 작동하지 않거나 커스터마이징이 필요한 경우:

### 1단계: 설정 파일 위치 확인

**설정 파일 경로**:
- **macOS/Linux**: `~/.claude/claude_code_config.json`
- **Windows**: `%USERPROFILE%\.claude\claude_code_config.json`

### 2단계: 설정 파일 생성/편집

```bash
# macOS/Linux
mkdir -p ~/.claude
nano ~/.claude/claude_code_config.json

# Windows (PowerShell)
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude"
notepad "$env:USERPROFILE\.claude\claude_code_config.json"
```

### 3단계: 설정 내용 추가

#### 기본 설정 (환경변수 사용)

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"]
    }
  }
}
```

**전제 조건**: `.env` 파일 또는 OS Keychain에 API 키가 저장되어 있어야 함

#### 명시적 API 키 설정

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-your-api-key-here"
      }
    }
  }
}
```

**⚠️ 주의**: API 키를 설정 파일에 직접 넣는 것은 권장하지 않습니다. 대신 OS Keychain을 사용하세요.

#### 커스텀 포트 설정

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start", "--port", "9000"],
      "env": {
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

#### 여러 MCP 서버 등록

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"]
    },
    "other-server": {
      "command": "node",
      "args": ["/path/to/other-server.js"]
    }
  }
}
```

---

## ✅ 설정 확인

### 방법 1: MCP 서버 목록 확인

```bash
claude mcp list
```

**정상 출력**:
```
Available MCP servers:
┌─────────────┬──────────┬───────┬──────────────┐
│ Name        │ Status   │ Tools │ Connected    │
├─────────────┼──────────┼───────┼──────────────┤
│ openrouter  │ running  │ 15    │ ✓            │
└─────────────┴──────────┴───────┴──────────────┘
```

### 방법 2: 툴 목록 확인

```bash
claude mcp tools openrouter
```

**출력 예시**:
```
OpenRouter MCP Tools:
1. chat_with_model - Chat with any OpenRouter model
2. list_available_models - List all available models
3. chat_with_vision - Vision-capable chat
4. list_vision_models - List vision models
5. collective_chat_completion - Multi-model consensus
6. ensemble_reasoning - Ensemble reasoning
7. adaptive_model_selection - Adaptive model selection
8. cross_model_validation - Cross-model validation
9. collaborative_problem_solving - Collaborative solving
10. benchmark_models - Benchmark models
... (15 tools total)
```

### 방법 3: 간단한 쿼리 테스트

```bash
claude "List all available AI models from OpenRouter"
```

**성공 시**: 모델 목록이 표시됨
**실패 시**: 아래 문제 해결 섹션 참조

---

## 💡 사용 예시

### 기본 채팅

```bash
# 기본 모델로 질문
claude "양자 컴퓨팅이 뭐야?"

# 특정 모델 지정
claude "Use GPT-4 to explain quantum computing"
claude "Use Claude Opus to write a Python function"
claude "Use Gemini Pro to analyze this code"
```

### 모델 발견

```bash
# 전체 모델 목록
claude "List all available AI models"

# 필터링
claude "Show me vision-capable models"
claude "List OpenAI models only"
claude "What are the cheapest models available?"
```

### 코드 작업

```bash
# 코드 리뷰
claude "Use Claude Opus to review the code in this directory"

# 코드 생성
claude "Use GPT-4 to write a binary search tree in Python"

# 리팩토링
claude "Use Claude Sonnet to refactor this function for better performance"
```

### Collective Intelligence 활용

```bash
# 다중 모델 합의
claude "Use consensus from 3 models to explain AI ethics"

# 복잡한 문제 해결
claude "Use ensemble reasoning to solve this algorithm problem"

# 검증
claude "Use cross-model validation to verify this answer"
```

### 이미지 분석

```bash
# 현재 디렉토리의 이미지
claude "Use GPT-4 Vision to analyze diagram.png"

# 스크린샷 분석
claude "Use Claude 3 Opus to describe screenshot.jpg"
```

### 비용 및 사용량 추적

```bash
# 사용량 확인
claude "Show my OpenRouter usage for this month"

# 비용 비교
claude "Compare costs of GPT-4 vs Claude Opus"

# 모델 통계
claude "Which models am I using most?"
```

---

## ⚙️ 고급 설정

### 1. 환경별 설정 분리

#### 개발 환경

**파일**: `~/.claude/claude_code_config.dev.json`

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

사용:
```bash
claude --config ~/.claude/claude_code_config.dev.json "테스트 쿼리"
```

#### 프로덕션 환경

**파일**: `~/.claude/claude_code_config.prod.json`

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

### 2. 보안 강화 설정

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "OPENROUTER_VERBOSE_LOGGING": "false",
        "LOG_LEVEL": "WARNING"
      }
    }
  },
  "security": {
    "requireConfirmation": true,
    "logAllQueries": true,
    "auditLogPath": "~/.claude/audit.log"
  }
}
```

### 3. 성능 최적화 설정

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "env": {
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

캐시 튜닝(TTL/메모리/파일 경로)은 환경변수가 아니라 코드에서 `ModelCache`로 조정합니다.

### 4. 팀 공유 설정

**`.claude/team_config.json`** (버전 관리에 추가 가능):

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start"],
      "description": "Team OpenRouter MCP Server",
      "env": {
        "OPENROUTER_APP_NAME": "TeamProject",
        "OPENROUTER_HTTP_REFERER": "https://team.example.com"
      }
    }
  }
}
```

**개인 설정** (`~/.claude/claude_code_config.json`):

```json
{
  "extends": "./.claude/team_config.json",
  "mcpServers": {
    "openrouter": {
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    }
  }
}
```

### 5. Alias 설정

**`.bashrc` 또는 `.zshrc`에 추가**:

```bash
# 자주 쓰는 명령어 alias
alias cc="claude-code"
alias cc-gpt4="claude-code 'Use GPT-4 to'"
alias cc-opus="claude-code 'Use Claude Opus to'"
alias cc-models="claude-code 'List all available models'"
alias cc-consensus="claude-code 'Use consensus from 3 models to'"

# 사용 예시
cc-gpt4 "explain this code"
cc-opus "review my Python function"
cc-models
cc-consensus "analyze this business problem"
```

---

## 🔍 문제 해결

### 1. "MCP server not found" 에러

**증상**:
```
Error: MCP server 'openrouter' not found
```

**해결**:
```bash
# 1. 설정 파일 존재 확인
ls ~/.claude/claude_code_config.json

# 2. 설정 파일 내용 검증 (JSON 문법 오류 확인)
cat ~/.claude/claude_code_config.json | python -m json.tool

# 3. 재설치
npx openrouter-mcp install-claude-code

# 4. Claude Code 재시작
```

### 2. "Server failed to start" 에러

**증상**:
```
Error: MCP server 'openrouter' failed to start
```

**해결**:
```bash
# 1. 수동으로 서버 시작해보기
npx openrouter-mcp start --debug

# 2. Python 설치 확인
python --version  # 3.9+ 필요

# 3. 의존성 재설치
cd ~/.npm-global/lib/node_modules/@physics91/openrouter-mcp
pip install -r requirements.txt

# 4. 포트 충돌 확인
lsof -i :8000  # 기본 포트
# 충돌 시 다른 포트 사용
```

**설정 파일에서 포트 변경**:
```json
{
  "mcpServers": {
    "openrouter": {
      "command": "npx",
      "args": ["openrouter-mcp", "start", "--port", "9000"]
    }
  }
}
```

### 3. API 키 인식 안 됨

**증상**:
```
Error: OPENROUTER_API_KEY not found
```

**해결**:

**방법 1: 초기화**:
```bash
npx openrouter-mcp init
```

**방법 2: 환경변수**:
```bash
# .bashrc 또는 .zshrc에 추가
export OPENROUTER_API_KEY="sk-or-v1-..."

# 적용
source ~/.bashrc  # 또는 ~/.zshrc
```

**방법 3: 설정 파일에 직접 (비권장)**:
```json
{
  "mcpServers": {
    "openrouter": {
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-..."
      }
    }
  }
}
```

### 4. Tools 목록이 비어있음

**증상**:
```bash
claude mcp tools openrouter
# No tools found
```

**해결**:
```bash
# 1. 서버 재시작
npx openrouter-mcp start --debug

# 2. 로그 확인
tail -f ~/.openrouter-mcp/logs/server.log

# 3. 수동 등록 확인
claude mcp reload openrouter
```

### 5. 설정 파일이 무시됨

**증상**: 설정을 변경해도 적용되지 않음

**해결**:
```bash
# 1. 설정 파일 위치 확인
claude config --show

# 2. 캐시 삭제
rm -rf ~/.claude/cache

# 3. 명시적 설정 파일 지정
claude --config ~/.claude/claude_code_config.json "테스트"

# 4. Claude Code 완전 재시작
pkill claude
claude --version  # 재시작
```

### 6. Windows에서 npx 명령 실행 안 됨

**증상**:
```
'npx' is not recognized as an internal or external command
```

**해결**:

**방법 1: Node.js 재설치**:
```powershell
# Node.js 최신 버전 설치
# https://nodejs.org/

# 설치 후 확인
npx --version
```

**방법 2: 전체 경로 사용**:
```json
{
  "mcpServers": {
    "openrouter": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": ["openrouter-mcp", "start"]
    }
  }
}
```

**방법 3: 글로벌 설치 후 직접 실행**:
```powershell
npm install -g @physics91/openrouter-mcp
```

```json
{
  "mcpServers": {
    "openrouter": {
      "command": "openrouter-mcp",
      "args": ["start"]
    }
  }
}
```

---

## 📊 설정 검증 체크리스트

설정 후 다음 항목들을 확인하세요:

- [ ] 설정 파일이 올바른 위치에 있음
  ```bash
  ls ~/.claude/claude_code_config.json
  ```

- [ ] JSON 문법이 올바름
  ```bash
  cat ~/.claude/claude_code_config.json | python -m json.tool
  ```

- [ ] MCP 서버가 목록에 표시됨
  ```bash
  claude mcp list
  ```

- [ ] Tools가 정상적으로 로드됨
  ```bash
  claude mcp tools openrouter
  ```

- [ ] 간단한 쿼리가 작동함
  ```bash
  claude "List available models"
  ```

- [ ] API 키가 인식됨
  ```bash
  npx openrouter-mcp status
  ```

---

## 🎯 Best Practices

### 1. 보안

✅ **DO**:
- OS Keychain 또는 환경변수 사용
- 설정 파일 권한 제한 (`chmod 600`)
- 주기적인 API 키 로테이션

❌ **DON'T**:
- 설정 파일에 API 키 직접 저장
- 설정 파일을 Git에 커밋
- Verbose 로깅을 프로덕션에서 활성화

### 2. 성능

✅ **DO**:
- 캐시 TTL 적절히 설정
- 자주 쓰는 alias 만들기
- 불필요한 verbose 로깅 비활성화

❌ **DON'T**:
- 매번 서버 재시작
- 과도하게 많은 MCP 서버 등록
- 너무 짧은 캐시 TTL 설정

### 3. 워크플로우

✅ **DO**:
- 팀 설정과 개인 설정 분리
- 환경별 설정 파일 사용
- 자주 쓰는 프롬프트를 alias로

❌ **DON'T**:
- 하나의 설정으로 모든 환경 사용
- 테스트 없이 프로덕션 설정 변경

---

## 📚 추가 리소스

- **전체 사용 가이드**: `docs/USAGE_GUIDE_KR.md`
- **빠른 시작**: `QUICKSTART.md`
- **보안 가이드**: `docs/SECURITY.md`
- **Claude Code 공식 문서**: https://docs.anthropic.com/claude-code
- **OpenRouter 문서**: https://openrouter.ai/docs

---

## 💬 도움이 필요하신가요?

- **GitHub Issues**: https://github.com/physics91/openrouter-mcp/issues
- **보안 문제**: `SECURITY.md` 참조
- **일반 질문**: Discussions 탭 이용

---

**마지막 업데이트**: 2025-11-18
**버전**: 1.3.0
