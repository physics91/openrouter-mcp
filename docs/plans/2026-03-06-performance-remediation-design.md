# OpenRouter MCP 성능 개선 설계

## 목표

OpenRouter MCP의 주요 성능 병목을 단계적으로 제거하되, 먼저 깨져 있는 baseline 테스트를 복구해 이후 성능 작업의 검증 기반을 안정화한다.

## 배경

현재 작업 전 baseline `quick` 테스트가 FastMCP API drift 때문에 실패한다. `get_tools()`와 `_tool_manager`에 기대는 오래된 테스트가 현재 FastMCP public API(`list_tools()`, `get_tool()`)와 맞지 않는다. 이 상태로는 이후 성능 패치의 성공/실패를 신뢰하기 어렵다.

## 설계 원칙

1. public API 우선
   테스트는 FastMCP 내부 구현이 아니라 `list_tools()` 반환값을 기준으로 검증한다.

2. 위험 우선순위 기반 단계 실행
   baseline 복구 후 `cache stampede -> semantic grouping -> benchmark 병렬화 -> iterative guard` 순으로 진행한다.

3. TDD와 작은 패치
   각 단계는 failing test, 최소 구현, 회귀 검증 순으로 진행한다.

4. 성능 최적화와 행위 보존 분리
   API/동작 변경 없이 내부 비용만 낮추는 패치를 우선한다.

## 접근안 비교

### 접근안 A: baseline 복구 후 단계별 패치

- baseline FastMCP 호환 테스트 복구
- cache refresh dedupe
- semantic grouping fast-path
- benchmark 병렬화
- collaborative/concurrency guard

장점:
- 검증 기반이 빠르게 회복된다.
- 변경 범위가 작아 회귀 추적이 쉽다.
- 각 최적화 효과를 분리 측정할 수 있다.

단점:
- 공통 유틸 정리는 뒤로 밀린다.

### 접근안 B: 성능 패치와 baseline 복구를 동시에 대규모 리팩터

장점:
- 한 번에 깔끔한 구조로 갈 수 있다.

단점:
- 원인 분리가 어려워진다.
- baseline이 깨진 상태에서 더 큰 리스크를 만든다.

## 선택

접근안 A를 채택한다.

## 컴포넌트별 설계

### 0단계: baseline 테스트 복구

- 대상 파일:
  - `tests/test_mcp_integration.py`
  - `tests/test_mcp_server_fixed.py`
- 설계:
  - 파일 내부 helper를 추가해 `await mcp.list_tools()` 결과를 `{tool.name: tool}` dict로 변환한다.
  - `_tool_manager._tools`와 `get_tools()` 사용을 모두 제거한다.
  - 테스트는 public API 기반 검증만 수행한다.

### 1단계: ModelCache refresh coalescing

- `ModelCache.get_models()`에 in-flight refresh 공유를 추가한다.
- 동시 다중 caller는 같은 fetch 결과를 await한다.
- 실패 시 in-flight 상태를 안전하게 해제한다.

### 2단계: semantic grouping fast-path

- 응답 수/길이 기반 early return 또는 저비용 prefilter를 추가한다.
- 비싼 pairwise similarity 비교 횟수를 줄인다.
- 품질 회귀를 막는 grouping 테스트를 유지한다.

### 3단계: benchmark 병렬화

- MCP benchmark wrapper가 병렬 경로를 사용할 수 있게 한다.
- 기본 동시성은 보수적으로 두고 옵션화한다.
- 기존 직렬 동작이 꼭 필요한 경우 fallback을 남긴다.

### 4단계: iterative/concurrency guard

- `acquire_model_slot()`에 timeout 또는 wait budget을 넣는다.
- iterative solver는 반복 중 조기 종료/진단 로그를 더 명확히 한다.

## 검증 전략

- baseline 복구:
  - `python3 run_tests.py quick -v`
  - 관련 MCP registration 테스트 파일 단독 실행

- 성능 단계:
  - 단계별 대상 테스트
  - 관련 회귀 테스트
  - 필요 시 로컬 마이크로벤치 재실행

## 비목표

- FastMCP 내부 구조에 맞춘 compatibility shim을 production 코드에 추가하지 않는다.
- free router와 단건 model lookup 최적화는 1차 병목 해결 후 재평가한다.
