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
from ..runtime_thrift import (
    compact_messages_for_model,
    enrich_response_with_thrift_metadata,
    get_request_thrift_metrics_snapshot,
    thrift_request_scope,
)
from ..utils.async_utils import collect_async_iterable

logger = logging.getLogger(__name__)

_router: Optional[FreeModelRouter] = None
_router_lock: Optional[asyncio.Lock] = None
_metrics: Optional[MetricsCollector] = None
_classifier: Optional[TaskClassifier] = None
_quota: Optional[QuotaTracker] = None
_native_fallback_disabled: bool = False


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
    global _router, _metrics, _classifier, _quota, _native_fallback_disabled
    _router = None
    _metrics = None
    _classifier = None
    _quota = None
    _native_fallback_disabled = False


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
    max_tokens: int = Field(FreeChatConfig.MAX_TOKENS, description="Maximum tokens to generate")
    temperature: float = Field(ModelDefaults.TEMPERATURE, description="Sampling temperature")
    preferred_models: List[str] = Field(
        default_factory=list, description="Preferred free model IDs (optional override)"
    )
    stream: bool = Field(
        False, description="Buffer streamed response (still returns complete result)"
    )


def _extract_text_for_classification(
    message: Union[str, List[Dict[str, Any]]],
) -> str:
    """Extract text content from a message for classifier input."""
    if isinstance(message, str):
        return message
    return " ".join(
        str(part.get("text", ""))
        for part in message
        if isinstance(part, dict) and part.get("type") == "text"
    )


def _infer_required_capabilities(
    messages: List[Dict[str, Any]],
) -> Optional[Dict[str, bool]]:
    """Infer required model capabilities from message content."""
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return {"supports_vision": True}
    return None


async def _execute_chat(
    client: Any,
    model_id: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    stream: bool,
    fallback_models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute a chat completion (streaming or non-streaming) and return unified result.

    When *fallback_models* is provided (non-streaming only), OpenRouter's native
    fallback is used: the API picks the first available model from the list.
    The ``actual_model`` key in the result holds the model that was actually used
    (may differ from *model_id* when fallback occurred).
    """
    compaction = await compact_messages_for_model(
        client,
        model_id,
        messages,
        max_completion_tokens=max_tokens,
    )
    effective_messages = compaction.messages

    if not stream:
        kwargs: Dict[str, Any] = {}
        if fallback_models:
            kwargs["models"] = fallback_models
        response = await client.chat_completion(
            model=model_id,
            messages=effective_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            **kwargs,
        )
        content = ""
        choices = response.get("choices") or []
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        return {
            "content": content,
            "usage": response.get("usage", {}),
            "streamed": False,
            "actual_model": response.get("model"),
        }

    # Streaming: buffer chunks then return complete result (no native fallback)
    chunks = await collect_async_iterable(
        client.stream_chat_completion(
            model=model_id,
            messages=effective_messages,
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
        "actual_model": None,
    }


async def _try_native_fallback(
    router: FreeModelRouter,
    client: Any,
    metrics: MetricsCollector,
    task_type: FreeTaskType,
    messages: List[Dict[str, Any]],
    request: "FreeChatRequest",
    required_caps: Optional[Dict[str, bool]],
) -> Optional[Dict[str, Any]]:
    """Attempt OpenRouter native fallback with ``models`` array.

    Returns the result dict on success, or ``None`` to fall through to the
    local retry loop.  Disables native fallback for the process lifetime
    if the API returns 400 for the ``models`` parameter.
    """
    global _native_fallback_disabled

    model_ids = await router.select_models(
        count=FreeChatConfig.NATIVE_FALLBACK_MODEL_LIMIT,
        preferred_models=request.preferred_models or None,
        task_type=task_type,
        required_capabilities=required_caps,
    )

    start_time = time.monotonic()
    try:
        exec_result = await _execute_chat(
            client,
            model_ids[0],
            messages,
            request.temperature,
            request.max_tokens,
            False,
            fallback_models=model_ids,
        )
        elapsed_ms = (time.monotonic() - start_time) * 1000
        return await _build_result(
            client,
            model_ids[0],
            exec_result,
            task_type,
            metrics,
            elapsed_ms,
        )

    except InvalidRequestError as e:
        err_msg = str(e).lower()
        if "models" in err_msg and (
            "parameter" in err_msg or "unknown" in err_msg or "array" in err_msg
        ):
            _native_fallback_disabled = True
            logger.info("Native fallback disabled: 'models' parameter not supported")
            return None
        raise

    except RateLimitError as e:
        # OpenRouter does not report which model in the array was rate-limited,
        # so we attribute the failure to the primary model.
        metrics.record_failure(model_ids[0], "RateLimitError")
        cooldown = (
            e.retry_after if e.retry_after is not None else FreeChatConfig.DEFAULT_COOLDOWN_SECONDS
        )
        router.report_rate_limit(model_ids[0], cooldown_seconds=cooldown)
        return None

    except (AuthenticationError,):
        raise

    except OpenRouterError as e:
        metrics.record_failure(model_ids[0], type(e).__name__)
        router.report_rate_limit(model_ids[0])
        return None


async def _build_result(
    client: Any,
    model_id: str,
    exec_result: Dict[str, Any],
    task_type: FreeTaskType,
    metrics: MetricsCollector,
    elapsed_ms: float,
) -> Dict[str, Any]:
    """Record metrics and build the final response dictionary."""
    actual_model = exec_result.get("actual_model") or model_id
    usage = exec_result["usage"]
    total_tokens = usage.get("total_tokens", 0)
    metrics.record_success(actual_model, elapsed_ms, total_tokens)
    thrift_metrics = get_request_thrift_metrics_snapshot()
    return await enrich_response_with_thrift_metadata(
        client=client,
        model=actual_model,
        payload={
            "model_used": actual_model,
            "response": exec_result["content"],
            "usage": usage,
            "task_type": task_type.value,
            "streamed": exec_result["streamed"],
        },
        thrift_metrics=thrift_metrics,
        total_cost_override_usd=0.0,
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
    with thrift_request_scope():
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

        # Reset native fallback flag when cache expires (retry opportunity)
        global _native_fallback_disabled
        if _native_fallback_disabled and router.is_cache_expired() is True:
            _native_fallback_disabled = False

        # Non-streaming: try OpenRouter native fallback (models array) first
        if not request.stream and not _native_fallback_disabled:
            result = await _try_native_fallback(
                router,
                client,
                metrics,
                task_type,
                messages,
                request,
                required_caps,
            )
            if result is not None:
                return result

        # Streaming or native fallback unavailable: local retry loop
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
                    client,
                    model_id,
                    messages,
                    request.temperature,
                    request.max_tokens,
                    request.stream,
                )
                elapsed_ms = (time.monotonic() - start_time) * 1000
                return await _build_result(
                    client,
                    model_id,
                    exec_result,
                    task_type,
                    metrics,
                    elapsed_ms,
                )

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
