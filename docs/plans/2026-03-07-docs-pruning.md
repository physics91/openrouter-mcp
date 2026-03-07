# Documentation Pruning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 고아 문서와 오래된 진입 문서를 제거하고, 남아 있는 핵심 문서의 링크만 복구해 문서 체계를 단순화한다.

**Architecture:** `README.md`를 단일 루트 진입점으로 삼고, 설치/통합/보안/한국어 상세 문서를 기능별 진입점으로 유지한다. 삭제 전에 참조 링크를 재배치하고, 삭제 후 고아 참조가 남지 않도록 검색 기반으로 검증한다.

**Tech Stack:** Markdown, ripgrep, git diff

---

### Task 1: Identify and fix inbound references

**Files:**
- Modify: `README.md`
- Modify: `docs/INSTALLATION.md`
- Modify: `docs/CLAUDE_DESKTOP_GUIDE.md`
- Modify: `docs/API.md`
- Modify: `docs/BENCHMARK_GUIDE.md`
- Modify: `docs/CLAUDE_CODE_SETUP_KR.md`
- Modify: `docs/USAGE_GUIDE_KR.md`

**Step 1: Keep current references visible**

Run:
```bash
rg -n "QUICKSTART.md|INDEX.md|PROJECT_STRUCTURE_GUIDE.md|MCP_CLI_GUIDE.md|SECURITY_QUICKSTART.md|CLAUDE_CODE_QUICKREF.md" README.md docs tests
```

Expected:
- 삭제 대상 문서를 가리키는 참조 위치가 출력된다.

**Step 2: Rewrite links to surviving documents**

- `INDEX.md` 참조는 제거하거나 인접한 실제 가이드로 대체
- `CLAUDE_CODE_QUICKREF.md` 참조는 `docs/CLAUDE_CODE_SETUP_KR.md`로 이동
- `QUICKSTART.md` 참조는 `README.md` 또는 관련 상세 가이드로 이동

**Step 3: Verify edited references**

Run:
```bash
rg -n "QUICKSTART.md|INDEX.md|CLAUDE_CODE_QUICKREF.md" README.md docs tests
```

Expected:
- 의도적으로 남긴 참조만 보이거나 결과가 비어 있다.

### Task 2: Remove obsolete documentation files

**Files:**
- Delete: `QUICKSTART.md`
- Delete: `docs/INDEX.md`
- Delete: `docs/PROJECT_STRUCTURE_GUIDE.md`
- Delete: `docs/MCP_CLI_GUIDE.md`
- Delete: `docs/SECURITY_QUICKSTART.md`
- Delete: `docs/CLAUDE_CODE_QUICKREF.md`

**Step 1: Delete only approved files**

- 승인된 6개 문서만 제거

**Step 2: Check repository status**

Run:
```bash
git status --short
```

Expected:
- 삭제 대상이 `D`로 표시되고 수정 문서가 `M`으로 표시된다.

### Task 3: Validate no stale references remain

**Files:**
- No code changes expected

**Step 1: Search for deleted file names**

Run:
```bash
rg -n "QUICKSTART.md|INDEX.md|PROJECT_STRUCTURE_GUIDE.md|MCP_CLI_GUIDE.md|SECURITY_QUICKSTART.md|CLAUDE_CODE_QUICKREF.md" README.md docs tests
```

Expected:
- 삭제 대상 파일명 참조가 더 이상 남지 않는다.

**Step 2: Review change summary**

Run:
```bash
git diff --stat
```

Expected:
- 핵심 문서 수정 + 승인된 문서 삭제만 포함된다.

**Step 3: Final sanity check**

Run:
```bash
git diff -- README.md docs/INSTALLATION.md docs/CLAUDE_DESKTOP_GUIDE.md docs/API.md docs/BENCHMARK_GUIDE.md docs/CLAUDE_CODE_SETUP_KR.md docs/USAGE_GUIDE_KR.md
```

Expected:
- 링크 정리 중심의 변경만 보인다.
