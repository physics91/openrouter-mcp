# Free Chat Tool Design

## Overview

OpenRouter의 무료 모델만 사용하여 비용 0원으로 AI 채팅을 제공하는 MCP tool.
여러 free 모델을 스마트 로테이션하여 rate limit를 예방하고, 품질 우선 가중치로 최적 모델을 자동 선택한다.

## MCP Tool Interface

```python
@mcp.tool()
async def free_chat(
    message: str,                    # 사용자 메시지
    system_prompt: str = "",         # 시스템 프롬프트 (선택)
    conversation_history: list = [], # 이전 대화 (선택)
    max_tokens: int = 4096,          # 최대 토큰
    temperature: float = 0.7,        # 온도
    preferred_models: list = [],     # 선호 모델 오버라이드 (선택)
) -> dict:
    # 반환: { model_used, response, tokens_used, models_available }
```

- 기존 `chat_with_model()`은 모델 직접 지정 필수
- `free_chat()`은 모델을 자동 선택 — 메시지만 보내면 됨
- `preferred_models`로 선호도 오버라이드 가능

## Architecture

### Weighted Priority Queue 방식

1. 서버 시작 시 `ModelCache.filter_models(free_only=True)` 활용하여 free 모델 목록 조회
2. 각 모델에 품질 점수 부여 (context length 40%, 모델 패밀리 평판 40%, 지원 기능 20%)
3. 동일 점수대 모델들 사이에서 round-robin 로테이션으로 rate limit 예방
4. Rate limit(429) 발생 시 해당 모델 cooldown 등록, 다음 우선순위 모델로 전환

### 품질 점수 산출

| 요소 | 가중치 | 기준 |
|------|--------|------|
| Context Length | 40% | 길수록 높은 점수 (128K > 32K > 8K) |
| 모델 패밀리 평판 | 40% | gemma-3 > llama > qwen > mistral > 기타 |
| 지원 기능 | 20% | vision, function calling 지원 시 가산점 |

### 로테이션 & Fallback 흐름

```
[품질 Tier 1] gemma-3-27b → llama-4-scout (round-robin)
     ↓ rate limit 시
[품질 Tier 2] qwen-2.5 → mistral-small (round-robin)
     ↓ rate limit 시
[품질 Tier 3] ...
     ↓ 모든 모델 소진 시
에러: "모든 free 모델이 사용 불가합니다. N초 후 재시도해주세요."
```

### 에러 처리

```
요청 → 모델 선택 → API 호출
                      ├─ 성공 → 응답 반환
                      ├─ 429 Rate Limit → cooldown 등록 → 다음 모델로 재시도 (최대 3회)
                      ├─ 503/502 → 다음 모델로 재시도
                      └─ 모든 모델 소진 → 에러 반환 (남은 cooldown 시간 포함)
```

## File Structure

### 새로 추가할 파일

```
src/openrouter_mcp/
├── handlers/
│   └── free_chat.py          # free_chat MCP tool 핸들러
├── free/
│   ├── __init__.py
│   └── router.py             # FreeModelRouter 클래스
```

### 기존 코드 재사용 (DRY)

| 기존 모듈 | 활용 방식 |
|-----------|-----------|
| `models/cache.py` | `ModelCache.filter_models(free_only=True)`로 free 모델 조회 |
| `client/openrouter.py` | `chat_completion()`, `RateLimitError` 재사용 |
| `utils/token_counter.py` | 토큰 카운팅 |
| `config/constants.py` | FreeChatConfig 상수 클래스 추가 |
| `mcp_registry.py` | `mcp`, `get_openrouter_client()` 재사용 |

### 수정할 기존 파일

- `config/constants.py` — `FreeChatConfig` 클래스 추가
- `server.py` — `handlers.free_chat` import 추가
- `handlers/__init__.py` — export 추가

## Core Component: FreeModelRouter

```python
class FreeModelRouter:
    """Free 모델 자동 선택 + 스마트 로테이션 + cooldown 관리"""

    def __init__(self, model_cache: ModelCache):
        self._cache = model_cache
        self._cooldowns: Dict[str, float] = {}  # model_id → cooldown_until timestamp
        self._usage_counts: Dict[str, int] = {}  # 로테이션용 사용 카운트

    async def select_model(self, preferred_models: list = None) -> str:
        """최적의 free 모델 선택 (품질 우선 + 로테이션)"""

    def report_rate_limit(self, model_id: str, cooldown_seconds: float = 60.0) -> None:
        """rate limit 발생 시 cooldown 등록"""

    def _score_model(self, model: dict) -> float:
        """모델 품질 점수 산출 (0.0 ~ 1.0)"""

    def _is_available(self, model_id: str) -> bool:
        """cooldown 중이 아닌 모델인지 확인"""

    def _cleanup_expired_cooldowns(self) -> None:
        """만료된 cooldown 항목 정리"""
```

## Constants (FreeChatConfig)

```python
class FreeChatConfig:
    DEFAULT_COOLDOWN_SECONDS: float = 60.0
    MAX_RETRY_COUNT: int = 3
    MAX_TOKENS: int = 4096
    CONTEXT_LENGTH_WEIGHT: float = 0.4
    REPUTATION_WEIGHT: float = 0.4
    FEATURES_WEIGHT: float = 0.2
    MODEL_REPUTATION: dict = {
        "google": 0.9,    # gemma-3
        "meta": 0.85,     # llama
        "qwen": 0.8,      # qwen
        "mistral": 0.75,  # mistral
    }
```
