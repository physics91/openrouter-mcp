from unittest.mock import Mock, call

import pytest

import src.openrouter_mcp.runtime_thrift.metrics as metrics_module

pytestmark = pytest.mark.unit


class _TrackingRequestMetrics:
    def __init__(self, events, value):
        self.events = events
        self.value = value

    def get(self):
        self.events.append(("context_get",))
        return self.value


def test_request_recording_pipeline_preserves_order_and_identity(monkeypatch):
    events = []
    request_metrics = object()
    first_arg = object()
    second_arg = object()

    def collector_recorder(*args):
        events.append(("collector", args))

    def request_recorder(target, *args):
        events.append(("request", target, args))

    monkeypatch.setattr(
        metrics_module,
        "_request_metrics_var",
        _TrackingRequestMetrics(events, request_metrics),
    )

    metrics_module._record_global_and_request(
        collector_recorder,
        request_recorder,
        first_arg,
        second_arg,
    )

    expected_args = (first_arg, second_arg)
    assert events == [
        ("collector", expected_args),
        ("context_get",),
        ("request", request_metrics, expected_args),
    ]


def test_request_recording_pipeline_preserves_missing_scope_bypass(monkeypatch):
    events = []
    collector_recorder = Mock()
    request_recorder = Mock()
    monkeypatch.setattr(
        metrics_module,
        "_request_metrics_var",
        _TrackingRequestMetrics(events, None),
    )

    metrics_module._record_global_and_request(
        collector_recorder,
        request_recorder,
        "value",
    )

    collector_recorder.assert_called_once_with("value")
    request_recorder.assert_not_called()
    assert events == [("context_get",)]


def test_request_recording_pipeline_preserves_collector_failure(monkeypatch):
    class FatalRecord(BaseException):
        pass

    context = Mock()
    collector_recorder = Mock(side_effect=FatalRecord("collector failed"))
    request_recorder = Mock()
    monkeypatch.setattr(metrics_module, "_request_metrics_var", context)

    with pytest.raises(FatalRecord, match="collector failed"):
        metrics_module._record_global_and_request(
            collector_recorder,
            request_recorder,
            "value",
        )

    context.get.assert_not_called()
    request_recorder.assert_not_called()


def test_request_recording_pipeline_preserves_context_failure(monkeypatch):
    collector_recorder = Mock()
    request_recorder = Mock()
    context = Mock()
    context.get.side_effect = RuntimeError("context failed")
    monkeypatch.setattr(metrics_module, "_request_metrics_var", context)

    with pytest.raises(RuntimeError, match="context failed"):
        metrics_module._record_global_and_request(
            collector_recorder,
            request_recorder,
            "value",
        )

    collector_recorder.assert_called_once_with("value")
    request_recorder.assert_not_called()


def test_request_recording_pipeline_preserves_local_failure(monkeypatch):
    request_metrics = object()
    collector_recorder = Mock()
    request_recorder = Mock(side_effect=RuntimeError("request failed"))
    context = Mock()
    context.get.return_value = request_metrics
    monkeypatch.setattr(metrics_module, "_request_metrics_var", context)

    with pytest.raises(RuntimeError, match="request failed"):
        metrics_module._record_global_and_request(
            collector_recorder,
            request_recorder,
            "value",
        )

    collector_recorder.assert_called_once_with("value")
    request_recorder.assert_called_once_with(request_metrics, "value")


@pytest.mark.parametrize(
    ("function_name", "collector_method", "request_recorder", "args"),
    [
        (
            "record_coalesced_savings",
            "record_coalesced_savings",
            "_record_coalesced_savings_on_metrics",
            (1, 2, 0.3),
        ),
        (
            "record_recent_reuse_savings",
            "record_recent_reuse_savings",
            "_record_recent_reuse_savings_on_metrics",
            (3, 4, 0.5),
        ),
        (
            "record_compaction_savings",
            "record_compaction_savings",
            "_record_compaction_savings_on_metrics",
            (6,),
        ),
        (
            "record_deferred_requests",
            "record_deferred_requests",
            "_record_deferred_requests_on_metrics",
            (7,),
        ),
        (
            "record_model_request",
            "record_model_request",
            "_record_model_request_on_metrics",
            ("provider/model",),
        ),
        (
            "record_prompt_cache_activity",
            "record_prompt_cache_activity",
            "_record_prompt_cache_activity_on_metrics",
            (8, 9, 0.1, "provider/model"),
        ),
    ],
)
def test_exported_recorders_delegate_request_pipeline(
    monkeypatch,
    function_name,
    collector_method,
    request_recorder,
    args,
):
    collector = Mock()
    record_pipeline = Mock()
    context = Mock()
    context.get.return_value = None
    monkeypatch.setattr(metrics_module, "_collector", collector)
    monkeypatch.setattr(metrics_module, "_request_metrics_var", context)
    monkeypatch.setattr(
        metrics_module,
        "_record_global_and_request",
        record_pipeline,
        raising=False,
    )

    getattr(metrics_module, function_name)(*args)

    assert record_pipeline.call_args_list == [
        call(
            getattr(collector, collector_method),
            getattr(metrics_module, request_recorder),
            *args,
        )
    ]
