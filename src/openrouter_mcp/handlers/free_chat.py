"""Free chat MCP tool handler -- zero-cost AI chat using free OpenRouter models."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..client.openrouter import (
    AuthenticationError,
    InvalidRequestError,
    OpenRouterError,
    RateLimitError,
)
from ..config.constants import FreeChatConfig, ModelDefaults
from ..free.classifier import FreeTaskType, TaskClassifier
from ..free.metrics import MetricsCollector
from ..free.quota import QuotaTracker
from ..free.router import FreeModelRouter
from ..mcp_registry import get_openrouter_client, mcp
from ..utils.async_utils import collect_async_iterable

logger = logging.getLogger(__name__)

_router: Optional[FreeModelRouter] = None
_router_lock: Optional[asyncio.Lock] = None
_metrics: Optional[MetricsCollector] = None
_classifier: Optional[TaskClassifier] = None
_quota: Optional[QuotaTracker] = None


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
        _metrics = MetricsCollector(
            persistence_path=FreeChatConfig.METRICS_CACHE_FILE,
        )
    return _metrics


def _get_metrics_for_shutdown() -> Optional[MetricsCollector]:
    """Return the existing MetricsCollector singleton, or None if not initialized."""
    return _metrics


def _get_classifier() -> TaskClassifier:
    """Get or create the module-level TaskClassifier singleton.

    Safe under single-threaded asyncio (GIL + no await points).
    """
    global _classifier
    if _classifier is None:
        _classifier = TaskClassifier()
    return _classifier


def _get_quota() -> QuotaTracker:
    """Get or create the module-level QuotaTracker singleton.

    Safe under single-threaded asyncio (GIL + no await points).
    """
    global _quota
    if _quota is None:
        _quota = QuotaTracker()
    return _quota


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
    global _router, _metrics, _classifier, _quota
    _router = None
    _metrics = None
    _classifier = None
    _quota = None


# Keep backward-compatible alias
reset_router = reset_handler_state


class FreeChatRequest(BaseModel):
    """Request for free chat completion."""

    message: Union[str, List[Dict[str, Any]]] = Field(
        ..., description="User message (string or multimodal content parts)"
    )
    system_prompt: str = Field("", description="System prompt (optional)")
    conversation_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="Previous conversation messages"
    )
    max_tokens: int = Field(
        FreeChatConfig.MAX_TOKENS, description="Maximum tokens to generate"
    )
    temperature: float = Field(
        ModelDefaults.TEMPERATURE, description="Sampling temperature"
    )
    preferred_models: List[str] = Field(
        default_factory=list, description="Preferred free model IDs (optional override)"
    )
    stream: bool = Field(False, description="Buffer streamed response (still returns complete result)")


def _extract_text_for_classification(
    message: Union[str, List[Dict[str, Any]]],
) -> str:
    """Extract text content from a message for classifier input."""
    if isinstance(message, str):
        return message
    return " ".join(
        part.get("text", "") for part in message if part.get("type") == "text"
    )


def _infer_required_capabilities(
    messages: List[Dict[str, Any]],
) -> Optional[Dict[str, bool]]:
    """Infer required model capabilities from message content."""
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    return {"supports_vision": True}
    return None


async def _execute_chat(
    client: Any,
    model_id: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    stream: bool,
) -> Dict[str, Any]:
    """Execute a chat completion (streaming or non-streaming) and return unified result."""
    if not stream:
        response = await client.chat_completion(
            model=model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        content = ""
        choices = response.get("choices") or []
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        return {
            "content": content,
            "usage": response.get("usage", {}),
            "streamed": False,
        }

    # Streaming: buffer chunks then return complete result
    chunks = await collect_async_iterable(
        client.stream_chat_completion(
            model=model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )
    parts: List[str] = []
    usage: Dict[str, Any] = {}
    for chunk in chunks:
        choices = chunk.get("choices") or []
        if choices:
            delta = choices[0].get("delta") or {}
            text = delta.get("content")
            if text:
                parts.append(text)
        chunk_usage = chunk.get("usage")
        if chunk_usage:
            usage = chunk_usage

    return {
        "content": "".join(parts),
        "usage": usage,
        "streamed": True,
    }


def _build_result(
    model_id: str,
    exec_result: Dict[str, Any],
    task_type: FreeTaskType,
    metrics: MetricsCollector,
    elapsed_ms: float,
) -> Dict[str, Any]:
    """Record metrics and build the final response dictionary."""
    usage = exec_result["usage"]
    total_tokens = usage.get("total_tokens", 0)
    metrics.record_success(model_id, elapsed_ms, total_tokens)
    return {
        "model_used": model_id,
        "response": exec_result["content"],
        "usage": usage,
        "task_type": task_type.value,
        "streamed": exec_result["streamed"],
    }


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
    quota = _get_quota()

    # Check quota before proceeding
    await quota.reserve_and_record()

    # Classify task type (extract text from multimodal messages)
    text_for_classify = _extract_text_for_classification(request.message)
    task_type = classifier.classify(text_for_classify, request.system_prompt)

    # Build messages
    messages: List[Dict[str, Any]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.extend(request.conversation_history)
    messages.append({"role": "user", "content": request.message})

    # Infer required capabilities from messages
    required_caps = _infer_required_capabilities(messages)

    last_error: Optional[Exception] = None

    for _attempt in range(FreeChatConfig.MAX_RETRY_COUNT + 1):
        try:
            model_id = await router.select_model(
                preferred_models=request.preferred_models or None,
                task_type=task_type,
                required_capabilities=required_caps,
            )
        except RuntimeError:
            raise

        start_time = time.monotonic()
        try:
            exec_result = await _execute_chat(
                client, model_id, messages,
                request.temperature, request.max_tokens, request.stream,
            )
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return _build_result(model_id, exec_result, task_type, metrics, elapsed_ms)

        except RateLimitError as e:
            logger.warning(f"Rate limit hit for {model_id}, trying next model")
            metrics.record_failure(model_id, "RateLimitError")
            cooldown = (
                e.retry_after
                if e.retry_after is not None
                else FreeChatConfig.DEFAULT_COOLDOWN_SECONDS
            )
            router.report_rate_limit(model_id, cooldown_seconds=cooldown)
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
    models_info = await router.list_models_with_status()
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
            "error_counts": dict(m.error_counts),
        }

    return {
        "models": models,
        "total_models_tracked": len(models),
        "quota": _get_quota().get_quota_status(),
    }
