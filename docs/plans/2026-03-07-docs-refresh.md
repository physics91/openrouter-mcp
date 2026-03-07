# Documentation Accuracy Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 삭제 이후 남은 핵심 문서에서 현재 CLI/패키지 정보와 어긋나는 안내를 고쳐 사용자가 실제로 따라 할 수 있는 문서 상태로 만든다.

**Architecture:** 실제 기준은 `bin/openrouter-mcp.js --help`와 현재 패키지 메타데이터, 그리고 `PYTHONPATH=src` 환경에서 확인한 도구 등록 결과로 잡는다. 문서 내용은 가능한 한 숫자와 고정 문자열 의존을 줄이고, 존재하지 않는 명령은 현재 지원되는 명령으로 대체한다.

**Tech Stack:** Markdown, ripgrep, Node CLI, Python import smoke check

---

### Task 1: Align package/install command names

**Files:**
- Modify: `docs/INSTALLATION.md`
- Modify: `docs/CLAUDE_CODE_GUIDE.md`
- Modify: `docs/CLAUDE_DESKTOP_GUIDE.md`
- Modify: `docs/USAGE_GUIDE_KR.md`
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Find stale unscoped package usage**

Run:
```bash
rg -n "npx openrouter-mcp|npm install -g openrouter-mcp|npm update -g openrouter-mcp|npm uninstall -g openrouter-mcp" docs/*.md
```

Expected:
- `npx`와 global install 예시가 현재 npm package name과 어긋나는 위치가 출력된다.

**Step 2: Rewrite commands**

- one-off 실행은 `npx @physics91/openrouter-mcp ...`
- global install/update/uninstall은 `@physics91/openrouter-mcp`
- global binary examples는 `openrouter-mcp ...` 유지

**Step 3: Verify**

Run:
```bash
rg -n "npx openrouter-mcp|npm install -g openrouter-mcp|npm update -g openrouter-mcp|npm uninstall -g openrouter-mcp" docs/*.md
```

Expected:
- 결과가 비어 있거나 의도된 예외만 남는다.

### Task 2: Remove unsupported CLI guidance

**Files:**
- Modify: `docs/INSTALLATION.md`
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `docs/USAGE_GUIDE_KR.md`
- Modify: `docs/MIGRATION_GUIDE.md`
- Modify: `docs/ENCRYPTION_V2.md`

**Step 1: Find unsupported commands**

Run:
```bash
rg -n "diagnose|check-env|status --diagnostic|export-key|import-key|migrate$|migrate " docs/*.md
```

Expected:
- 현재 CLI에 없는 명령이 출력된다.

**Step 2: Rewrite or remove**

- `diagnose`, `check-env`, `status --diagnostic`는 `status`, `start --debug`, 관련 파일 확인 절차로 대체
- `export-key`, `import-key`는 제거하고 현재 CLI가 제공하지 않음을 반영
- `migrate`는 `migrate-encryption`으로 정정

**Step 3: Verify against CLI**

Run:
```bash
node bin/openrouter-mcp.js --help
node bin/openrouter-mcp.js status --help
node bin/openrouter-mcp.js start --help
```

Expected:
- 문서에 남긴 명령이 실제 help 출력과 모순되지 않는다.

### Task 3: Clean deleted-doc links and stale placeholders

**Files:**
- Modify: `docs/SECURE_STORAGE_INTEGRATION.md`
- Modify: `docs/QUICK_REFERENCE.md`
- Modify: `docs/FAQ.md`
- Modify: `docs/INSTALLATION.md`

**Step 1: Find stale references**

Run:
```bash
rg -n "SECURITY_QUICKSTART.md|your-repo/issues|yourusername" docs/*.md README.md
```

Expected:
- 삭제된 문서 링크와 placeholder GitHub 링크가 출력된다.

**Step 2: Rewrite links**

- `SECURITY_QUICKSTART.md`는 `SECURITY.md` 등 살아 있는 문서로 대체
- placeholder GitHub issues 링크는 실제 저장소 URL로 수정

**Step 3: Verify**

Run:
```bash
rg -n "SECURITY_QUICKSTART.md|your-repo/issues|yourusername" docs/*.md README.md
```

Expected:
- 결과가 비어 있다.

### Task 4: Update tool/model count language

**Files:**
- Modify: `docs/API.md`
- Modify: `docs/CLAUDE_CODE_GUIDE.md`
- Modify: `docs/CLAUDE_DESKTOP_GUIDE.md`
- Modify: `docs/CLAUDE_CODE_SETUP_KR.md`
- Modify: `docs/FAQ.md`
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Verify current tool count**

Run:
```bash
PYTHONPATH=src python - <<'PY'
import asyncio
from openrouter_mcp.handlers import register_handlers
from openrouter_mcp.mcp_registry import mcp
async def main():
    register_handlers()
    print(len(await mcp.list_tools()))
asyncio.run(main())
PY
```

Expected:
- 현재 tool count가 출력된다.

**Step 2: Rewrite brittle copy**

- 고정 model count는 `OpenRouter models`, `multiple AI models` 같은 표현으로 완화
- tool count example은 현재 값 기준으로 정정하거나 count 의존을 줄인다

**Step 3: Final diff check**

Run:
```bash
git diff --stat
```

Expected:
- 문서 수정만 포함되고 삭제 범위가 예상과 맞는다.
