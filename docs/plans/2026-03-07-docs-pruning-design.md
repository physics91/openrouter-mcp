# 문서 슬림화 설계

## 목표

현재 저장소에서 실제 진입점 역할을 하지 않거나, 코드/CLI와 어긋나거나, 유지 비용만 높이는 문서를 우선 제거해 문서 체계를 단순화한다.

## 배경

문서 수가 많아지면서 다음 문제가 겹쳐 있다.

1. `README.md`, `QUICKSTART.md`, `docs/INDEX.md`가 모두 시작점 역할을 하며 동선이 분산되어 있다.
2. 일부 문서는 현재 코드와 맞지 않는다. 예: `docs/MCP_CLI_GUIDE.md`의 `claude_mcp.py`, `docs/PROJECT_STRUCTURE_GUIDE.md`의 오래된 구조 설명.
3. 일부 문서는 저장소 내 참조가 없거나, 다른 문서와 강하게 중복된다.

## 설계 원칙

1. 단일 진입점 유지
   빠른 시작은 `README.md`, 상세 설정은 기능별 가이드 문서로 모은다.

2. 잘못된 문서 우선 제거
   고아 문서보다도, 현재 동작과 어긋나는 문서를 먼저 제거한다.

3. 삭제 전 링크 복구
   삭제 대상 문서를 참조하는 링크는 남길 문서로 먼저 재배치한다.

4. 이번 단계는 구조 단순화까지만
   대규모 문서 재작성이나 내용 통합은 다음 단계로 미룬다.

## 접근안 비교

### 접근안 A: 보수적 삭제

- 고아 문서와 명백한 구버전 문서만 제거

장점:
- 위험이 가장 낮다.

단점:
- 시작점 중복과 문서 동선 혼잡이 그대로 남는다.

### 접근안 B: 중간 강도 정리

- 고아 문서 + 일부 중복 문서 제거

장점:
- 리스크와 효과의 균형이 좋다.

단점:
- `README.md`와 별도 quick start/인덱스 이중 구조가 남는다.

### 접근안 C: 공격적 축소

- 고아 문서, 중복 문서, 별도 진입점 문서를 함께 제거
- `README.md`를 루트 진입점으로 고정

장점:
- 문서 구조가 가장 단순해진다.
- 신규 사용자의 시작 지점이 명확해진다.

단점:
- 링크 정리 범위가 넓다.
- 남길 문서의 역할이 상대적으로 커진다.

## 선택

접근안 C를 채택한다.

## 삭제 범위

- `QUICKSTART.md`
- `docs/INDEX.md`
- `docs/PROJECT_STRUCTURE_GUIDE.md`
- `docs/MCP_CLI_GUIDE.md`
- `docs/SECURITY_QUICKSTART.md`
- `docs/CLAUDE_CODE_QUICKREF.md`

## 유지 범위

- `README.md`
- `docs/INSTALLATION.md`
- `docs/CLAUDE_DESKTOP_GUIDE.md`
- `docs/CLAUDE_CODE_GUIDE.md`
- `docs/CLAUDE_CODE_SETUP_KR.md`
- `docs/USAGE_GUIDE_KR.md`
- `docs/SECURITY.md`

## 링크 정리 전략

- `README.md`의 `docs/INDEX.md`, `QUICKSTART.md` 참조 제거
- 삭제 문서를 참조하던 한국어 문서는 남길 상세 가이드로 재연결
- 설치/통합/API/벤치마크 문서의 `INDEX.md` 참조 제거

## 검증 전략

1. 삭제 대상 파일명으로 저장소 전체 검색
2. 삭제 후 잔여 참조가 없는지 확인
3. `git diff --stat`로 변경 범위 확인

## 비목표

- 남아 있는 문서의 전면 재작성
- 문서 국제화 체계 개편
- 문서 내용 최신화 전수 점검
