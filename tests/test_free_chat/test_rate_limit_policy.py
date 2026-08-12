from contextlib import nullcontext
from unittest.mock import AsyncMock, Mock, call

import pytest

import src.openrouter_mcp.handlers.free_chat as handler
from src.openrouter_mcp.client.openrouter import RateLimitError
from src.openrouter_mcp.free.classifier import FreeTaskType

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("retry_after", "expected_cooldown"),
    [
        (None, 60.0),
        (0.0, 0.0),
        (-1.0, -1.0),
    ],
)
def test_record_rate_limit_failure_preserves_order_and_cooldown(
    retry_after,
    expected_cooldown,
):
    events = []
    router = Mock()
    metrics = Mock()
    error = RateLimitError("limited", retry_after=retry_after)
    metrics.record_failure.side_effect = lambda *args: events.append(("record", args))
    router.report_rate_limit.side_effect = lambda *args, **kwargs: events.append(
        ("report", args, kwargs)
    )

    handler._record_rate_limit_failure(router, metrics, "model-a", error)

    assert events == [
        ("record", ("model-a", "RateLimitError")),
        (
            "report",
            ("model-a",),
            {"cooldown_seconds": expected_cooldown},
        ),
    ]


def test_record_rate_limit_failure_stops_when_metrics_recording_fails():
    expected_error = RuntimeError("metrics failed")
    router = Mock()
    metrics = Mock()
    metrics.record_failure.side_effect = expected_error

    with pytest.raises(RuntimeError) as exc_info:
        handler._record_rate_limit_failure(
            router,
            metrics,
            "model-a",
            RateLimitError("limited"),
        )

    assert exc_info.value is expected_error
    router.report_rate_limit.assert_not_called()


def test_record_rate_limit_failure_propagates_router_failure_after_recording():
    expected_error = RuntimeError("router failed")
    router = Mock()
    router.report_rate_limit.side_effect = expected_error
    metrics = Mock()

    with pytest.raises(RuntimeError) as exc_info:
        handler._record_rate_limit_failure(
            router,
            metrics,
            "model-a",
            RateLimitError("limited", retry_after=2.0),
        )

    assert exc_info.value is expected_error
    metrics.record_failure.assert_called_once_with("model-a", "RateLimitError")


@pytest.mark.asyncio
async def test_native_fallback_delegates_rate_limit_for_primary_model(monkeypatch):
    error = RateLimitError("limited", retry_after=3.0)
    router = Mock()
    router.select_models = AsyncMock(return_value=["primary", "fallback"])
    metrics = Mock()
    record_failure = Mock()
    monkeypatch.setattr(handler, "_execute_chat", AsyncMock(side_effect=error))
    monkeypatch.setattr(handler, "_record_rate_limit_failure", record_failure)

    result = await handler._try_native_fallback(
        router,
        object(),
        metrics,
        FreeTaskType.GENERAL,
        [{"role": "user", "content": "hi"}],
        handler.FreeChatRequest(message="hi"),
        None,
    )

    assert result is None
    record_failure.assert_called_once_with(router, metrics, "primary", error)


@pytest.mark.asyncio
async def test_local_retry_logs_then_delegates_rate_limit_and_continues(monkeypatch):
    events = []
    error = RateLimitError("limited", retry_after=0.0)
    router = Mock()
    router.is_cache_expired.return_value = False
    router.select_model = AsyncMock(side_effect=["model-a", "model-b"])
    client = object()
    metrics = Mock()
    classifier = Mock()
    classifier.classify.return_value = FreeTaskType.GENERAL
    quota = Mock()
    quota.reserve_and_record = AsyncMock()
    exec_result = {
        "content": "ok",
        "usage": {},
        "streamed": False,
        "actual_model": None,
    }
    built_result = {"result": "ok"}

    monkeypatch.setattr(handler, "_get_router", AsyncMock(return_value=router))
    monkeypatch.setattr(
        handler,
        "get_openrouter_client",
        AsyncMock(return_value=client),
    )
    monkeypatch.setattr(handler, "_get_metrics", Mock(return_value=metrics))
    monkeypatch.setattr(handler, "_get_classifier", Mock(return_value=classifier))
    monkeypatch.setattr(handler, "_get_quota", Mock(return_value=quota))
    monkeypatch.setattr(handler, "_try_native_fallback", AsyncMock(return_value=None))
    monkeypatch.setattr(
        handler,
        "_execute_chat",
        AsyncMock(side_effect=[error, exec_result]),
    )
    monkeypatch.setattr(
        handler,
        "_build_result",
        AsyncMock(return_value=built_result),
    )
    monkeypatch.setattr(handler, "thrift_request_scope", nullcontext)
    monkeypatch.setattr(
        handler.logger,
        "warning",
        Mock(side_effect=lambda message: events.append(("warning", message))),
    )

    def record_failure(received_router, received_metrics, model_id, received_error):
        events.append(("record", model_id))
        assert received_router is router
        assert received_metrics is metrics
        assert received_error is error

    monkeypatch.setattr(handler, "_record_rate_limit_failure", record_failure)

    result = await handler.free_chat(handler.FreeChatRequest(message="hi"))

    assert result is built_result
    assert events == [
        ("warning", "Rate limit hit for model-a, trying next model"),
        ("record", "model-a"),
    ]
    assert router.select_model.await_args_list == [
        call(
            preferred_models=None,
            task_type=FreeTaskType.GENERAL,
            required_capabilities=None,
        ),
        call(
            preferred_models=None,
            task_type=FreeTaskType.GENERAL,
            required_capabilities=None,
        ),
    ]
