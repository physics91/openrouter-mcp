# Free Chat Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** OpenRouter의 무료 모델만 사용하여 비용 0원 AI 채팅을 제공하는 `free_chat` MCP tool 구현

**Architecture:** `FreeModelRouter`가 `ModelCache.filter_models(free_only=True)`로 free 모델을 조회하고, 품질 가중치 기반 priority queue + round-robin 로테이션으로 최적 모델을 자동 선택한다. Rate limit 시 cooldown 등록 후 다음 모델로 fallback.

**Tech Stack:** Python 3.9+, FastMCP, httpx, pydantic, pytest + pytest-asyncio

---

### Task 1: FreeChatConfig 상수 추가

**Files:**
- Modify: `src/openrouter_mcp/config/constants.py:135-146`
- Test: `tests/test_free_chat/test_constants.py`

**Step 1: Write the failing test**

Create `tests/test_free_chat/__init__.py` (empty) and `tests/test_free_chat/test_constants.py`:

```python
import pytest
from src.openrouter_mcp.config.constants import FreeChatConfig


class TestFreeChatConfig:
    @pytest.mark.unit
    def test_default_cooldown_seconds(self):
        assert FreeChatConfig.DEFAULT_COOLDOWN_SECONDS == 60.0

    @pytest.mark.unit
    def test_max_retry_count(self):
        assert FreeChatConfig.MAX_RETRY_COUNT == 3

    @pytest.mark.unit
    def test_max_tokens(self):
        assert FreeChatConfig.MAX_TOKENS == 4096

    @pytest.mark.unit
    def test_scoring_weights_sum_to_one(self):
        total = (
            FreeChatConfig.CONTEXT_LENGTH_WEIGHT
            + FreeChatConfig.REPUTATION_WEIGHT
            + FreeChatConfig.FEATURES_WEIGHT
        )
        assert abs(total - 1.0) < 1e-9

    @pytest.mark.unit
    def test_model_reputation_has_known_providers(self):
        assert "google" in FreeChatConfig.MODEL_REPUTATION
        assert "meta" in FreeChatConfig.MODEL_REPUTATION

    @pytest.mark.unit
    def test_default_reputation_score(self):
        assert FreeChatConfig.DEFAULT_REPUTATION == 0.5
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_free_chat/test_constants.py -v`
Expected: FAIL with `ImportError: cannot import name 'FreeChatConfig'`

**Step 3: Write minimal implementation**

Add to `src/openrouter_mcp/config/constants.py` before `__all__`:

```python
class FreeChatConfig:
    """Configuration for free_chat tool."""

    DEFAULT_COOLDOWN_SECONDS: float = 60.0
    MAX_RETRY_COUNT: int = 3
    MAX_TOKENS: int = 4096
    CONTEXT_LENGTH_WEIGHT: float = 0.4
    REPUTATION_WEIGHT: float = 0.4
    FEATURES_WEIGHT: float = 0.2
    DEFAULT_REPUTATION: float = 0.5
    MODEL_REPUTATION: dict = {
        "google": 0.9,
        "meta": 0.85,
        "qwen": 0.8,
        "mistral": 0.75,
        "microsoft": 0.7,
        "deepseek": 0.7,
    }
```

Also add `"FreeChatConfig"` to `__all__` list.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_free_chat/test_constants.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add tests/test_free_chat/ src/openrouter_mcp/config/constants.py
git commit -m "feat: add FreeChatConfig constants for free_chat tool"
```

---

### Task 2: FreeModelRouter - 모델 점수 산출

**Files:**
- Create: `src/openrouter_mcp/free/__init__.py`
- Create: `src/openrouter_mcp/free/router.py`
- Test: `tests/test_free_chat/test_router_scoring.py`

**Step 1: Write the failing test**

Create `tests/test_free_chat/test_router_scoring.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.openrouter_mcp.free.router import FreeModelRouter


@pytest.fixture
def mock_model_cache():
    cache = MagicMock()
    cache.filter_models.return_value = []
    return cache


@pytest.fixture
def router(mock_model_cache):
    return FreeModelRouter(mock_model_cache)


@pytest.fixture
def free_model_google():
    return {
        "id": "google/gemma-3-27b-it:free",
        "name": "Gemma 3 27B",
        "context_length": 131072,
        "cost_tier": "free",
        "provider": "google",
        "capabilities": {
            "supports_vision": True,
            "supports_function_calling": False,
        },
    }


@pytest.fixture
def free_model_meta():
    return {
        "id": "meta-llama/llama-4-scout:free",
        "name": "Llama 4 Scout",
        "context_length": 32768,
        "cost_tier": "free",
        "provider": "meta",
        "capabilities": {
            "supports_vision": False,
            "supports_function_calling": False,
        },
    }


@pytest.fixture
def free_model_unknown():
    return {
        "id": "unknown-org/some-model:free",
        "name": "Some Model",
        "context_length": 8192,
        "cost_tier": "free",
        "provider": "unknown",
        "capabilities": {},
    }


class TestFreeModelRouterScoring:
    @pytest.mark.unit
    def test_score_google_model_higher_than_meta(self, router, free_model_google, free_model_meta):
        """Google model (longer context + higher reputation) scores higher than Meta."""
        score_google = router._score_model(free_model_google)
        score_meta = router._score_model(free_model_meta)
        assert score_google > score_meta

    @pytest.mark.unit
    def test_score_meta_higher_than_unknown(self, router, free_model_meta, free_model_unknown):
        """Known provider scores higher than unknown."""
        score_meta = router._score_model(free_model_meta)
        score_unknown = router._score_model(free_model_unknown)
        assert score_meta > score_unknown

    @pytest.mark.unit
    def test_score_range_is_zero_to_one(self, router, free_model_google):
        score = router._score_model(free_model_google)
        assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_score_vision_bonus(self, router, free_model_google, free_model_meta):
        """Vision support gives a score bonus."""
        # Google has vision=True, Meta has vision=False
        # Even with same context + provider, vision adds bonus
        score_google = router._score_model(free_model_google)
        # Override google to no-vision for comparison
        no_vision = {**free_model_google, "capabilities": {"supports_vision": False, "supports_function_calling": False}}
        score_no_vision = router._score_model(no_vision)
        assert score_google > score_no_vision

    @pytest.mark.unit
    def test_score_empty_capabilities(self, router, free_model_unknown):
        """Model with empty capabilities still gets a valid score."""
        score = router._score_model(free_model_unknown)
        assert 0.0 <= score <= 1.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_free_chat/test_router_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.openrouter_mcp.free'`

**Step 3: Write minimal implementation**

Create `src/openrouter_mcp/free/__init__.py`:

```python
"""Free model routing for zero-cost AI chat."""
```

Create `src/openrouter_mcp/free/router.py`:

```python
"""Free model router with quality-weighted selection and smart rotation."""

import logging
import time
from typing import Dict, List, Optional

from ..config.constants import FreeChatConfig
from ..models.cache import ModelCache
from ..utils.metadata import extract_provider_from_id

logger = logging.getLogger(__name__)

# Max context length used for normalization (256K tokens)
_MAX_CONTEXT_LENGTH = 262144


class FreeModelRouter:
    """Selects the best available free model using quality scoring and rotation."""

    def __init__(self, model_cache: ModelCache) -> None:
        self._cache = model_cache
        self._cooldowns: Dict[str, float] = {}
        self._usage_counts: Dict[str, int] = {}

    def _score_model(self, model: dict) -> float:
        """Score a model from 0.0 to 1.0 based on quality heuristics."""
        # Context length score (0.0 to 1.0)
        context_length = model.get("context_length", 0)
        context_score = min(context_length / _MAX_CONTEXT_LENGTH, 1.0)

        # Provider reputation score (0.0 to 1.0)
        provider = model.get("provider", "")
        if not provider or provider == "unknown":
            provider = extract_provider_from_id(model.get("id", "")).value
        reputation = FreeChatConfig.MODEL_REPUTATION.get(
            provider.lower(), FreeChatConfig.DEFAULT_REPUTATION
        )

        # Feature score (0.0 to 1.0)
        caps = model.get("capabilities", {})
        feature_score = 0.0
        if caps.get("supports_vision", False):
            feature_score += 0.5
        if caps.get("supports_function_calling", False):
            feature_score += 0.5

        return (
            FreeChatConfig.CONTEXT_LENGTH_WEIGHT * context_score
            + FreeChatConfig.REPUTATION_WEIGHT * reputation
            + FreeChatConfig.FEATURES_WEIGHT * feature_score
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_free_chat/test_router_scoring.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/openrouter_mcp/free/ tests/test_free_chat/test_router_scoring.py
git commit -m "feat: add FreeModelRouter with quality scoring"
```

---

### Task 3: FreeModelRouter - Cooldown 관리

**Files:**
- Modify: `src/openrouter_mcp/free/router.py`
- Test: `tests/test_free_chat/test_router_cooldown.py`

**Step 1: Write the failing test**

Create `tests/test_free_chat/test_router_cooldown.py`:

```python
import time
import pytest
from unittest.mock import MagicMock

from src.openrouter_mcp.free.router import FreeModelRouter


@pytest.fixture
def mock_model_cache():
    cache = MagicMock()
    cache.filter_models.return_value = []
    return cache


@pytest.fixture
def router(mock_model_cache):
    return FreeModelRouter(mock_model_cache)


class TestCooldownManagement:
    @pytest.mark.unit
    def test_model_available_by_default(self, router):
        assert router._is_available("google/gemma-3:free") is True

    @pytest.mark.unit
    def test_report_rate_limit_makes_unavailable(self, router):
        router.report_rate_limit("google/gemma-3:free")
        assert router._is_available("google/gemma-3:free") is False

    @pytest.mark.unit
    def test_cooldown_expires(self, router):
        router.report_rate_limit("google/gemma-3:free", cooldown_seconds=0.1)
        assert router._is_available("google/gemma-3:free") is False
        time.sleep(0.15)
        assert router._is_available("google/gemma-3:free") is True

    @pytest.mark.unit
    def test_cleanup_expired_cooldowns(self, router):
        router.report_rate_limit("model-a", cooldown_seconds=0.1)
        router.report_rate_limit("model-b", cooldown_seconds=10.0)
        time.sleep(0.15)
        router._cleanup_expired_cooldowns()
        assert "model-a" not in router._cooldowns
        assert "model-b" in router._cooldowns

    @pytest.mark.unit
    def test_multiple_rate_limits(self, router):
        router.report_rate_limit("model-a")
        router.report_rate_limit("model-b")
        assert router._is_available("model-a") is False
        assert router._is_available("model-b") is False
        assert router._is_available("model-c") is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_free_chat/test_router_cooldown.py -v`
Expected: FAIL with `AttributeError: 'FreeModelRouter' object has no attribute '_is_available'`

**Step 3: Write minimal implementation**

Add to `FreeModelRouter` in `src/openrouter_mcp/free/router.py`:

```python
    def _is_available(self, model_id: str) -> bool:
        """Check if a model is not in cooldown."""
        cooldown_until = self._cooldowns.get(model_id)
        if cooldown_until is None:
            return True
        return time.time() >= cooldown_until

    def report_rate_limit(
        self, model_id: str, cooldown_seconds: float = FreeChatConfig.DEFAULT_COOLDOWN_SECONDS
    ) -> None:
        """Register a model for cooldown after rate limit."""
        self._cooldowns[model_id] = time.time() + cooldown_seconds
        logger.info(f"Model {model_id} in cooldown for {cooldown_seconds}s")

    def _cleanup_expired_cooldowns(self) -> None:
        """Remove expired cooldown entries."""
        now = time.time()
        self._cooldowns = {
            mid: until for mid, until in self._cooldowns.items() if until > now
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_free_chat/test_router_cooldown.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/openrouter_mcp/free/router.py tests/test_free_chat/test_router_cooldown.py
git commit -m "feat: add cooldown management to FreeModelRouter"
```

---

### Task 4: FreeModelRouter - select_model (모델 선택 + 로테이션)

**Files:**
- Modify: `src/openrouter_mcp/free/router.py`
- Test: `tests/test_free_chat/test_router_selection.py`

**Step 1: Write the failing test**

Create `tests/test_free_chat/test_router_selection.py`:

```python
import pytest
from unittest.mock import MagicMock

from src.openrouter_mcp.free.router import FreeModelRouter


def _make_free_model(model_id, context_length=32768, provider="unknown"):
    return {
        "id": model_id,
        "name": model_id,
        "context_length": context_length,
        "cost_tier": "free",
        "provider": provider,
        "capabilities": {},
    }


@pytest.fixture
def free_models():
    return [
        _make_free_model("google/gemma-3-27b:free", 131072, "google"),
        _make_free_model("meta-llama/llama-4-scout:free", 131072, "meta"),
        _make_free_model("qwen/qwen-2.5:free", 32768, "qwen"),
    ]


@pytest.fixture
def mock_cache(free_models):
    cache = MagicMock()
    cache.filter_models.return_value = free_models
    return cache


@pytest.fixture
def router(mock_cache):
    return FreeModelRouter(mock_cache)


class TestSelectModel:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_selects_highest_quality_first(self, router):
        model_id = await router.select_model()
        # Google has highest reputation + long context
        assert model_id == "google/gemma-3-27b:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rotates_on_repeated_calls(self, router):
        first = await router.select_model()
        second = await router.select_model()
        # Should rotate to avoid same model repeatedly
        assert first != second

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_skips_cooldown_models(self, router):
        router.report_rate_limit("google/gemma-3-27b:free")
        model_id = await router.select_model()
        assert model_id != "google/gemma-3-27b:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_when_all_models_exhausted(self, router):
        router.report_rate_limit("google/gemma-3-27b:free")
        router.report_rate_limit("meta-llama/llama-4-scout:free")
        router.report_rate_limit("qwen/qwen-2.5:free")
        with pytest.raises(RuntimeError, match="사용 가능한 free 모델이 없습니다"):
            await router.select_model()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_preferred_models_override(self, router):
        model_id = await router.select_model(preferred_models=["qwen/qwen-2.5:free"])
        assert model_id == "qwen/qwen-2.5:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_preferred_model_skipped_if_cooldown(self, router):
        router.report_rate_limit("qwen/qwen-2.5:free")
        model_id = await router.select_model(preferred_models=["qwen/qwen-2.5:free"])
        # Falls back to normal selection since preferred is in cooldown
        assert model_id != "qwen/qwen-2.5:free"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_free_models_available(self):
        cache = MagicMock()
        cache.filter_models.return_value = []
        router = FreeModelRouter(cache)
        with pytest.raises(RuntimeError, match="사용 가능한 free 모델이 없습니다"):
            await router.select_model()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_free_chat/test_router_selection.py -v`
Expected: FAIL with `AttributeError: 'FreeModelRouter' object has no attribute 'select_model'`

**Step 3: Write minimal implementation**

Add to `FreeModelRouter` in `src/openrouter_mcp/free/router.py`:

```python
    async def select_model(self, preferred_models: Optional[List[str]] = None) -> str:
        """Select the best available free model."""
        self._cleanup_expired_cooldowns()

        # Get free models from cache
        free_models = self._cache.filter_models(free_only=True)

        if not free_models:
            raise RuntimeError("사용 가능한 free 모델이 없습니다. 캐시를 새로고침해주세요.")

        # Try preferred models first
        if preferred_models:
            for pref_id in preferred_models:
                if self._is_available(pref_id):
                    self._usage_counts[pref_id] = self._usage_counts.get(pref_id, 0) + 1
                    return pref_id

        # Filter available models and score them
        candidates = [
            (model, self._score_model(model))
            for model in free_models
            if self._is_available(model["id"])
        ]

        if not candidates:
            soonest = min(self._cooldowns.values()) - time.time() if self._cooldowns else 0
            raise RuntimeError(
                f"사용 가능한 free 모델이 없습니다. {max(0, soonest):.0f}초 후 재시도해주세요."
            )

        # Sort by score descending, then by usage count ascending (least used first)
        candidates.sort(key=lambda x: (-x[1], self._usage_counts.get(x[0]["id"], 0)))

        selected = candidates[0][0]
        model_id = selected["id"]
        self._usage_counts[model_id] = self._usage_counts.get(model_id, 0) + 1

        logger.info(f"Selected free model: {model_id} (score={candidates[0][1]:.3f})")
        return model_id
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_free_chat/test_router_selection.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add src/openrouter_mcp/free/router.py tests/test_free_chat/test_router_selection.py
git commit -m "feat: add select_model with rotation and fallback to FreeModelRouter"
```

---

### Task 5: free_chat MCP tool 핸들러

**Files:**
- Create: `src/openrouter_mcp/handlers/free_chat.py`
- Test: `tests/test_free_chat/test_free_chat_handler.py`

**Step 1: Write the failing test**

Create `tests/test_free_chat/test_free_chat_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.openrouter_mcp.handlers.free_chat import free_chat, FreeChatRequest
from src.openrouter_mcp.client.openrouter import RateLimitError, OpenRouterError


@pytest.fixture
def mock_chat_response():
    return {
        "id": "gen-free-001",
        "model": "google/gemma-3-27b:free",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "안녕하세요!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


class TestFreeChatHandler:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_free_chat(self, mock_chat_response):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = mock_chat_response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(
                message="안녕!",
            )
            result = await free_chat.fn(request)

            assert result["model_used"] == "google/gemma-3-27b:free"
            assert result["response"] == "안녕하세요!"
            assert result["usage"]["total_tokens"] == 8

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rate_limit_triggers_fallback(self, mock_chat_response):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            # First call: rate limit, second call: success
            mock_client.chat_completion.side_effect = [
                RateLimitError("rate limited"),
                mock_chat_response,
            ]
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.side_effect = [
                "google/gemma-3-27b:free",
                "meta-llama/llama-4-scout:free",
            ]
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello")
            result = await free_chat.fn(request)

            assert result["model_used"] == "meta-llama/llama-4-scout:free"
            mock_router.report_rate_limit.assert_called_once_with("google/gemma-3-27b:free")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_models_exhausted(self):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.side_effect = RateLimitError("rate limited")
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.side_effect = [
                "model-a",
                "model-b",
                "model-c",
                RuntimeError("사용 가능한 free 모델이 없습니다"),
            ]
            mock_router.report_rate_limit = MagicMock()
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(message="Hello")
            with pytest.raises(RuntimeError, match="사용 가능한 free 모델이 없습니다"):
                await free_chat.fn(request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_system_prompt_included(self, mock_chat_response):
        with patch("src.openrouter_mcp.handlers.free_chat.get_openrouter_client") as mock_get_client, \
             patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_client = AsyncMock()
            mock_client.chat_completion.return_value = mock_chat_response
            mock_get_client.return_value = mock_client

            mock_router = AsyncMock()
            mock_router.select_model.return_value = "google/gemma-3-27b:free"
            mock_get_router.return_value = mock_router

            request = FreeChatRequest(
                message="What is Python?",
                system_prompt="You are a helpful assistant.",
            )
            await free_chat.fn(request)

            call_kwargs = mock_client.chat_completion.call_args[1]
            messages = call_kwargs["messages"]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are a helpful assistant."
            assert messages[1]["role"] == "user"

    @pytest.mark.unit
    def test_request_validation_defaults(self):
        request = FreeChatRequest(message="Hello")
        assert request.temperature == 0.7
        assert request.max_tokens == 4096
        assert request.system_prompt == ""
        assert request.conversation_history == []
        assert request.preferred_models == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_free_chat/test_free_chat_handler.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

Create `src/openrouter_mcp/handlers/free_chat.py`:

```python
"""Free chat MCP tool handler — zero-cost AI chat using free OpenRouter models."""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..mcp_registry import mcp, get_openrouter_client
from ..config.constants import FreeChatConfig, ModelDefaults
from ..free.router import FreeModelRouter
from ..client.openrouter import RateLimitError, OpenRouterError

logger = logging.getLogger(__name__)

# Module-level router singleton (lazy-initialized)
_router: Optional[FreeModelRouter] = None


async def _get_router() -> FreeModelRouter:
    """Get or create the module-level FreeModelRouter singleton."""
    global _router
    if _router is None:
        client = await get_openrouter_client()
        _router = FreeModelRouter(client._model_cache)
    return _router


class FreeChatRequest(BaseModel):
    """Request for free chat completion."""

    message: str = Field(..., description="User message to send")
    system_prompt: str = Field("", description="System prompt (optional)")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list, description="Previous conversation messages"
    )
    max_tokens: int = Field(FreeChatConfig.MAX_TOKENS, description="Maximum tokens to generate")
    temperature: float = Field(ModelDefaults.TEMPERATURE, description="Sampling temperature")
    preferred_models: List[str] = Field(
        default_factory=list, description="Preferred free model IDs (optional override)"
    )


@mcp.tool()
async def free_chat(request: FreeChatRequest) -> Dict[str, Any]:
    """
    Chat using free OpenRouter models with automatic model selection.

    Automatically selects the best available free model based on quality scoring.
    If a model hits its rate limit, transparently falls back to the next best model.
    Cost is always $0.

    Args:
        request: Free chat request with message and optional parameters.

    Returns:
        Dictionary with model_used, response text, and usage info.
    """
    router = await _get_router()
    client = await get_openrouter_client()

    # Build messages
    messages: List[Dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.extend(request.conversation_history)
    messages.append({"role": "user", "content": request.message})

    last_error: Optional[Exception] = None

    for attempt in range(FreeChatConfig.MAX_RETRY_COUNT + 1):
        try:
            model_id = await router.select_model(
                preferred_models=request.preferred_models or None
            )
        except RuntimeError:
            raise

        try:
            response = await client.chat_completion(
                model=model_id,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
            )

            content = ""
            choices = response.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")

            return {
                "model_used": model_id,
                "response": content,
                "usage": response.get("usage", {}),
            }

        except RateLimitError:
            logger.warning(f"Rate limit hit for {model_id}, trying next model")
            router.report_rate_limit(model_id)
            last_error = RateLimitError(f"Rate limited: {model_id}")
            continue

        except (OpenRouterError, Exception) as e:
            logger.error(f"Error with model {model_id}: {e}")
            last_error = e
            router.report_rate_limit(model_id)
            continue

    raise last_error or RuntimeError("사용 가능한 free 모델이 없습니다.")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_free_chat/test_free_chat_handler.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/openrouter_mcp/handlers/free_chat.py tests/test_free_chat/test_free_chat_handler.py
git commit -m "feat: add free_chat MCP tool handler with retry and fallback"
```

---

### Task 6: 서버 통합 (import 등록)

**Files:**
- Modify: `src/openrouter_mcp/server.py:61-72`
- Modify: `src/openrouter_mcp/handlers/__init__.py`
- Test: `tests/test_free_chat/test_registration.py`

**Step 1: Write the failing test**

Create `tests/test_free_chat/test_registration.py`:

```python
import pytest


class TestFreeChatRegistration:
    @pytest.mark.unit
    def test_free_chat_importable(self):
        from src.openrouter_mcp.handlers.free_chat import free_chat, FreeChatRequest
        assert free_chat is not None
        assert FreeChatRequest is not None

    @pytest.mark.unit
    def test_handlers_init_exports_free_chat(self):
        from src.openrouter_mcp.handlers import free_chat
        assert free_chat is not None

    @pytest.mark.unit
    def test_free_chat_request_model_validates(self):
        from src.openrouter_mcp.handlers.free_chat import FreeChatRequest
        req = FreeChatRequest(message="test")
        assert req.message == "test"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_free_chat/test_registration.py -v`
Expected: PASS for test 1 and 3, FAIL for test 2 (`free_chat` not in `handlers/__init__.py`)

**Step 3: Write minimal implementation**

Modify `src/openrouter_mcp/handlers/__init__.py` — add `free_chat`:

```python
"""
Handlers package for OpenRouter MCP Server.
"""

from . import chat
from . import multimodal
from . import mcp_benchmark
from . import collective_intelligence
from . import free_chat

__all__ = [
    "chat",
    "multimodal",
    "mcp_benchmark",
    "collective_intelligence",
    "free_chat",
]
```

Modify `src/openrouter_mcp/server.py` — add import at line 64:

```python
    from .handlers import free_chat  # noqa: F401
```

And in fallback block at line 72:

```python
    from openrouter_mcp.handlers import free_chat  # noqa: F401
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_free_chat/test_registration.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/openrouter_mcp/handlers/__init__.py src/openrouter_mcp/server.py tests/test_free_chat/test_registration.py
git commit -m "feat: register free_chat handler in server and handlers init"
```

---

### Task 7: list_free_models MCP tool (보조 도구)

**Files:**
- Modify: `src/openrouter_mcp/handlers/free_chat.py`
- Test: `tests/test_free_chat/test_list_free_models.py`

**Step 1: Write the failing test**

Create `tests/test_free_chat/test_list_free_models.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.openrouter_mcp.handlers.free_chat import list_free_models


@pytest.fixture
def free_models():
    return [
        {
            "id": "google/gemma-3-27b:free",
            "name": "Gemma 3 27B",
            "context_length": 131072,
            "cost_tier": "free",
            "provider": "google",
            "capabilities": {"supports_vision": True},
        },
        {
            "id": "meta-llama/llama-4-scout:free",
            "name": "Llama 4 Scout",
            "context_length": 131072,
            "cost_tier": "free",
            "provider": "meta",
            "capabilities": {},
        },
    ]


class TestListFreeModels:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lists_free_models_with_scores(self, free_models):
        with patch("src.openrouter_mcp.handlers.free_chat._get_router") as mock_get_router:
            mock_router = MagicMock()
            mock_router._cache.filter_models.return_value = free_models
            mock_router._score_model.side_effect = [0.85, 0.75]
            mock_router._is_available.return_value = True
            mock_get_router.return_value = mock_router

            result = await list_free_models.fn()

            assert len(result["models"]) == 2
            assert result["total_count"] == 2
            assert result["models"][0]["id"] == "google/gemma-3-27b:free"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_free_chat/test_list_free_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'list_free_models'`

**Step 3: Write minimal implementation**

Add to `src/openrouter_mcp/handlers/free_chat.py`:

```python
@mcp.tool()
async def list_free_models() -> Dict[str, Any]:
    """
    List all available free models with quality scores and availability status.

    Returns:
        Dictionary with models list, each including id, name, score, and availability.
    """
    router = await _get_router()
    free_models = router._cache.filter_models(free_only=True)

    models_info = []
    for model in free_models:
        models_info.append({
            "id": model.get("id", ""),
            "name": model.get("name", ""),
            "context_length": model.get("context_length", 0),
            "provider": model.get("provider", "unknown"),
            "quality_score": round(router._score_model(model), 3),
            "available": router._is_available(model.get("id", "")),
        })

    # Sort by quality score descending
    models_info.sort(key=lambda m: -m["quality_score"])

    return {
        "models": models_info,
        "total_count": len(models_info),
        "available_count": sum(1 for m in models_info if m["available"]),
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_free_chat/test_list_free_models.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/openrouter_mcp/handlers/free_chat.py tests/test_free_chat/test_list_free_models.py
git commit -m "feat: add list_free_models MCP tool for inspecting available free models"
```

---

### Task 8: 전체 테스트 스위트 실행 & 회귀 확인

**Files:**
- No new files

**Step 1: Run all existing tests to verify no regressions**

Run: `pytest tests/ -v --tb=short -x`
Expected: All existing tests still PASS

**Step 2: Run only free_chat tests**

Run: `pytest tests/test_free_chat/ -v`
Expected: All new tests PASS

**Step 3: Commit (if any fix needed)**

Only commit if regression fixes were required.

---

### Task 9: free/__init__.py 에 public API export 추가

**Files:**
- Modify: `src/openrouter_mcp/free/__init__.py`

**Step 1: Update init to export public API**

```python
"""Free model routing for zero-cost AI chat."""

from .router import FreeModelRouter

__all__ = ["FreeModelRouter"]
```

**Step 2: Verify import works**

Run: `python -c "from src.openrouter_mcp.free import FreeModelRouter; print('OK')"`
Expected: `OK`

**Step 3: Final commit**

```bash
git add src/openrouter_mcp/free/__init__.py
git commit -m "chore: export FreeModelRouter from free package"
```
