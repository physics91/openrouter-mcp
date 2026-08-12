from unittest.mock import AsyncMock, Mock, call

import pytest

import src.openrouter_mcp.handlers.mcp_benchmark as benchmark_module

pytestmark = pytest.mark.unit


class _TrackingFlag:
    def __init__(self, events, label, value):
        self.events = events
        self.label = label
        self.value = value

    def __bool__(self):
        self.events.append(("truth", self.label))
        return self.value


class _TrackingResult:
    def __init__(self, events, label, value):
        self.events = events
        self.label = label
        self.value = value

    @property
    def success(self):
        self.events.append(("success", self.label))
        return _TrackingFlag(self.events, self.label, self.value)


class _TrackingResults(dict):
    def __init__(self, events, *args, **kwargs):
        self.events = events
        super().__init__(*args, **kwargs)

    def items(self):
        self.events.append(("items",))
        return super().items()


def test_select_successful_results_preserves_order_truthiness_and_identity():
    events = []
    first = _TrackingResult(events, "first", True)
    second = _TrackingResult(events, "second", False)
    third = _TrackingResult(events, "third", True)
    results = _TrackingResults(
        events,
        [("first", first), ("second", second), ("third", third)],
    )

    selected = benchmark_module._select_successful_benchmark_results(results)

    assert events == [
        ("items",),
        ("success", "first"),
        ("truth", "first"),
        ("success", "second"),
        ("truth", "second"),
        ("success", "third"),
        ("truth", "third"),
    ]
    assert selected is not results
    assert list(selected) == ["first", "third"]
    assert selected["first"] is first
    assert selected["third"] is third


def test_select_successful_results_preserves_exception_short_circuit():
    events = []

    class FailingResult:
        @property
        def success(self):
            events.append(("success", "failing"))
            raise RuntimeError("selection failed")

    first = _TrackingResult(events, "first", True)
    third = _TrackingResult(events, "third", True)
    results = _TrackingResults(
        events,
        [("first", first), ("failing", FailingResult()), ("third", third)],
    )

    with pytest.raises(RuntimeError, match="selection failed"):
        benchmark_module._select_successful_benchmark_results(results)

    assert events == [
        ("items",),
        ("success", "first"),
        ("truth", "first"),
        ("success", "failing"),
    ]


def test_build_benchmark_data_delegates_success_selection(monkeypatch):
    results = {"model-a": Mock(success=False)}
    successful_results = {}
    select_successful = Mock(return_value=successful_results)
    monkeypatch.setattr(
        benchmark_module,
        "_select_successful_benchmark_results",
        select_successful,
        raising=False,
    )
    monkeypatch.setattr(
        benchmark_module,
        "_serialize_benchmark_result",
        Mock(return_value={}),
    )

    _, selected = benchmark_module._build_benchmark_data(
        results,
        timestamp="2026-08-13T00:00:00",
        models=["model-a"],
        prompt="prompt",
        runs=1,
        delay_seconds=0.0,
        include_prompts_in_logs=False,
    )

    assert selected is successful_results
    assert select_successful.call_args_list == [call(results)]


@pytest.mark.asyncio
async def test_category_comparison_delegates_success_selection(monkeypatch):
    models = [{"id": "model-a", "category": "chat", "quality_score": 1.0}]
    results = {"model-a": Mock(success=False)}
    successful_results = {}
    handler = Mock()
    handler.model_cache.get_models.return_value = models
    handler.benchmark_models = AsyncMock(return_value=results)
    select_successful = Mock(return_value=successful_results)
    group_results = Mock(return_value={})
    monkeypatch.setattr(
        benchmark_module,
        "get_benchmark_handler",
        AsyncMock(return_value=handler),
    )
    monkeypatch.setattr(
        benchmark_module,
        "_select_successful_benchmark_results",
        select_successful,
        raising=False,
    )
    monkeypatch.setattr(
        benchmark_module,
        "_group_category_benchmark_results",
        group_results,
    )

    await benchmark_module.compare_model_categories(categories=["chat"])

    assert select_successful.call_args_list == [call(results)]
    assert group_results.call_args.args[0] is successful_results


@pytest.mark.asyncio
async def test_performance_comparison_delegates_success_selection(monkeypatch):
    results = {"model-a": Mock(success=False)}
    successful_result = Mock()
    successful_results = {"model-a": successful_result}
    comparison_data = {"ranking": []}
    handler = Mock()
    handler.benchmark_models = AsyncMock(return_value=results)
    select_successful = Mock(return_value=successful_results)
    build_comparison = Mock(return_value=comparison_data)
    monkeypatch.setattr(
        benchmark_module,
        "get_benchmark_handler",
        AsyncMock(return_value=handler),
    )
    monkeypatch.setattr(
        benchmark_module,
        "_select_successful_benchmark_results",
        select_successful,
        raising=False,
    )
    monkeypatch.setattr(
        benchmark_module,
        "_build_performance_comparison_data",
        build_comparison,
    )

    result = await benchmark_module.compare_model_performance(["model-a"])

    assert result is comparison_data
    assert select_successful.call_args_list == [call(results)]
    assert build_comparison.call_args.args[0] is successful_results
