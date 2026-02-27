"""Free chat MCP tool handler -- zero-cost AI chat using free OpenRouter models."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..mcp_registry import mcp, get_openrouter_client
from ..config.constants import FreeChatConfig, ModelDefaults
from ..free.router import FreeModelRouter
from ..free.metrics import MetricsCollector
from ..free.classifier import TaskClassifier
from ..client.openrouter import RateLimitError, OpenRouterError, AuthenticationError, InvalidRequestError

logger = logging.getLogger(__name__)

_router: Optional[FreeModelRouter] = None
_router_lock: Optional[asyncio.Lock] = None
_metrics: Optional[MetricsCollector] = None
_classifier: Optional[TaskClassifier] = None


def _get_router_lock() -> asyncio.Lock:
    # Safe under single-threaded asyncio (GIL + cooperative scheduling)
    global _router_lock
    if _router_lock is None:
        _router_lock = asyncio.Lock()
    return _router_lock


def _get_metrics() -> MetricsCollector:
    """Get or create the module-level MetricsCollector singleton.

    Safe under single-threaded asyncio (GIL + no await points).
    """
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def _get_classifier() -> TaskClassifier:
    """Get or create the module-level TaskClassifier singleton.

    Safe under single-threaded asyncio (GIL + no await points).
    """
    global _classifier
    if _classifier is None:
        _classifier = TaskClassifier()
    return _classifier


async def _get_router() -> FreeModelRouter:
    """Get or create the module-level FreeModelRouter singleton."""
    global _router
    if _router is not None:
        return _router
    async with _get_router_lock():
        if _router is None:
            client = await get_openrouter_client()
            _router = FreeModelRouter(client.model_cache, metrics=_get_metrics())
    return _router


def reset_handler_state() -> None:
    """Reset all handler singletons. Called during shutdown or key rotation."""
    global _router, _metrics, _classifier
    _router = None
    _metrics = None
    _classifier = None


# Keep backward-compatible alias
reset_router = reset_handler_state


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
    metrics = _get_metrics()
    classifier = _get_classifier()

    # Classify task type
    task_type = classifier.classify(request.message, request.system_prompt)

    # Build messages
    messages: List[Dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.extend(request.conversation_history)
    messages.append({"role": "user", "content": request.message})

    last_error: Optional[Exception] = None

    for _attempt in range(FreeChatConfig.MAX_RETRY_COUNT + 1):
        try:
            model_id = await router.select_model(
                preferred_models=request.preferred_models or None,
                task_type=task_type,
            )
        except RuntimeError:
            raise

        start_time = time.monotonic()
        try:
            response = await client.chat_completion(
                model=model_id,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
            )

            elapsed_ms = (time.monotonic() - start_time) * 1000
            usage = response.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            metrics.record_success(model_id, elapsed_ms, total_tokens)

            content = ""
            choices = response.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")

            return {
                "model_used": model_id,
                "response": content,
                "usage": usage,
                "task_type": task_type.value,
            }

        except RateLimitError as e:
            logger.warning(f"Rate limit hit for {model_id}, trying next model")
            metrics.record_failure(model_id, "RateLimitError")
            router.report_rate_limit(model_id)
            last_error = e
            continue

        except (AuthenticationError, InvalidRequestError):
            raise

        except OpenRouterError as e:
            logger.error(f"OpenRouter error with model {model_id}: {e}")
            metrics.record_failure(model_id, type(e).__name__)
            last_error = e
            router.report_rate_limit(model_id)
            continue

    raise last_error or RuntimeError("사용 가능한 free 모델이 없습니다.")


@mcp.tool()
async def list_free_models() -> Dict[str, Any]:
    """List all available free models with quality scores and availability status."""
    router = await _get_router()
    models_info = router.list_models_with_status()
    return {
        "models": models_info,
        "total_count": len(models_info),
        "available_count": sum(1 for m in models_info if m["available"]),
    }


@mcp.tool()
async def get_free_model_metrics() -> Dict[str, Any]:
    """View performance metrics for free models (response time, success rate, throughput)."""
    metrics = _get_metrics()
    all_metrics = metrics.get_all_metrics()

    models: Dict[str, Any] = {}
    for model_id, m in all_metrics.items():
        models[model_id] = {
            "total_requests": m.total_requests,
            "success_count": m.success_count,
            "failure_count": m.failure_count,
            "success_rate": round(m.success_rate, 3),
            "avg_latency_ms": round(m.avg_latency_ms, 1),
            "tokens_per_second": round(m.tokens_per_second, 1),
            "performance_score": round(metrics.get_performance_score(model_id), 3),
        }

    return {
        "models": models,
        "total_models_tracked": len(models),
    }
