from unittest.mock import Mock, call

import pytest

import src.openrouter_mcp.runtime_thrift.metrics as metrics_module
from src.openrouter_mcp.runtime_thrift.metrics import ThriftMetricsCollector

pytestmark = pytest.mark.unit


class _TrackingLock:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append(("lock_enter",))

    def __exit__(self, exc_type, exc, traceback):
        self.events.append(("lock_exit", exc))
        return False


def _make_collector(events=None):
    collector = object.__new__(ThriftMetricsCollector)
    collector._metrics = []
    collector._lock = _TrackingLock(events if events is not None else [])
    return collector


def test_record_pipeline_preserves_lock_mutation_and_save_order(monkeypatch):
    events = []
    collector = _make_collector(events)
    daily_metrics = []
    first_arg = object()
    second_arg = object()

    def recorder(target, *args):
        events.append(("record", target, args))
        target.append(args)

    def get_current_day_metrics():
        events.append(("current_day",))
        return daily_metrics

    def auto_save():
        events.append(("auto_save",))

    monkeypatch.setattr(
        collector,
        "_get_current_day_metrics",
        get_current_day_metrics,
    )
    monkeypatch.setattr(collector, "_maybe_auto_save", auto_save)

    collector._record_on_aggregate_and_current_day(
        recorder,
        first_arg,
        second_arg,
    )

    expected_args = (first_arg, second_arg)
    assert events == [
        ("lock_enter",),
        ("record", collector._metrics, expected_args),
        ("current_day",),
        ("record", daily_metrics, expected_args),
        ("auto_save",),
        ("lock_exit", None),
    ]
    assert collector._metrics == [expected_args]
    assert daily_metrics == [expected_args]


def test_record_pipeline_preserves_aggregate_failure_state(monkeypatch):
    class FatalRecord(BaseException):
        pass

    events = []
    collector = _make_collector(events)
    get_current_day_metrics = Mock()
    auto_save = Mock()

    def recorder(target):
        target.append("mutated")
        raise FatalRecord("aggregate failed")

    monkeypatch.setattr(
        collector,
        "_get_current_day_metrics",
        get_current_day_metrics,
    )
    monkeypatch.setattr(collector, "_maybe_auto_save", auto_save)

    with pytest.raises(FatalRecord, match="aggregate failed"):
        collector._record_on_aggregate_and_current_day(recorder)

    assert collector._metrics == ["mutated"]
    get_current_day_metrics.assert_not_called()
    auto_save.assert_not_called()
    assert isinstance(events[-1][1], FatalRecord)


def test_record_pipeline_preserves_day_lookup_failure_state(monkeypatch):
    collector = _make_collector()
    auto_save = Mock()

    def recorder(target):
        target.append("mutated")

    monkeypatch.setattr(
        collector,
        "_get_current_day_metrics",
        Mock(side_effect=RuntimeError("day failed")),
    )
    monkeypatch.setattr(collector, "_maybe_auto_save", auto_save)

    with pytest.raises(RuntimeError, match="day failed"):
        collector._record_on_aggregate_and_current_day(recorder)

    assert collector._metrics == ["mutated"]
    auto_save.assert_not_called()


def test_record_pipeline_preserves_daily_failure_state(monkeypatch):
    collector = _make_collector()
    daily_metrics = []
    auto_save = Mock()

    def recorder(target):
        target.append("mutated")
        if target is daily_metrics:
            raise RuntimeError("daily failed")

    monkeypatch.setattr(
        collector,
        "_get_current_day_metrics",
        Mock(return_value=daily_metrics),
    )
    monkeypatch.setattr(collector, "_maybe_auto_save", auto_save)

    with pytest.raises(RuntimeError, match="daily failed"):
        collector._record_on_aggregate_and_current_day(recorder)

    assert collector._metrics == ["mutated"]
    assert daily_metrics == ["mutated"]
    auto_save.assert_not_called()


def test_record_pipeline_preserves_auto_save_failure_state(monkeypatch):
    collector = _make_collector()
    daily_metrics = []

    def recorder(target):
        target.append("mutated")

    monkeypatch.setattr(
        collector,
        "_get_current_day_metrics",
        Mock(return_value=daily_metrics),
    )
    monkeypatch.setattr(
        collector,
        "_maybe_auto_save",
        Mock(side_effect=RuntimeError("save failed")),
    )

    with pytest.raises(RuntimeError, match="save failed"):
        collector._record_on_aggregate_and_current_day(recorder)

    assert collector._metrics == ["mutated"]
    assert daily_metrics == ["mutated"]


@pytest.mark.parametrize(
    ("method_name", "recorder_name", "args"),
    [
        (
            "record_coalesced_savings",
            "_record_coalesced_savings_on_metrics",
            (1, 2, 0.3),
        ),
        (
            "record_recent_reuse_savings",
            "_record_recent_reuse_savings_on_metrics",
            (3, 4, 0.5),
        ),
        (
            "record_compaction_savings",
            "_record_compaction_savings_on_metrics",
            (6,),
        ),
        (
            "record_deferred_requests",
            "_record_deferred_requests_on_metrics",
            (7,),
        ),
        (
            "record_model_request",
            "_record_model_request_on_metrics",
            ("provider/model",),
        ),
        (
            "record_prompt_cache_activity",
            "_record_prompt_cache_activity_on_metrics",
            (8, 9, 0.1, "provider/model"),
        ),
    ],
)
def test_public_recorders_delegate_pipeline(
    monkeypatch,
    method_name,
    recorder_name,
    args,
):
    collector = object.__new__(ThriftMetricsCollector)
    record_pipeline = Mock()
    monkeypatch.setattr(
        collector,
        "_record_on_aggregate_and_current_day",
        record_pipeline,
        raising=False,
    )

    getattr(collector, method_name)(*args)

    assert record_pipeline.call_args_list == [
        call(getattr(metrics_module, recorder_name), *args)
    ]
