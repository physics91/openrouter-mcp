from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.openrouter_mcp.handlers import mcp_benchmark

pytestmark = pytest.mark.unit


def test_build_benchmark_data_preserves_pipeline_order_and_result_identity(monkeypatch):
    events = []
    successful = SimpleNamespace(success=True)
    failed = SimpleNamespace(success=False)
    results = {"model-a": successful, "model-b": failed}
    models = ["model-a", "model-b"]
    ranking = [(successful, 0.75)]
    serialized_ranking = [{"model_id": "model-a"}]
    analyzer = Mock()

    def serialize(result, include_response_content):
        events.append(("serialize", result))
        assert include_response_content is True
        return {"source": result}

    def create_analyzer():
        events.append(("analyzer", None))
        return analyzer

    def rank(received_results):
        events.append(("rank", received_results))
        assert received_results == [successful]
        assert received_results[0] is successful
        return ranking

    def serialize_ranking(received_ranking):
        events.append(("serialize-ranking", received_ranking))
        assert received_ranking is ranking
        return serialized_ranking

    analyzer.rank_models.side_effect = rank
    monkeypatch.setattr(mcp_benchmark, "_serialize_benchmark_result", serialize)
    monkeypatch.setattr(mcp_benchmark, "ModelPerformanceAnalyzer", create_analyzer)
    monkeypatch.setattr(
        mcp_benchmark, "_serialize_benchmark_ranking", serialize_ranking
    )

    data, successful_results = mcp_benchmark._build_benchmark_data(
        results,
        timestamp="2026-08-12T12:34:56",
        models=models,
        prompt="prompt",
        runs=2,
        delay_seconds=0.5,
        include_prompts_in_logs=True,
    )

    assert data == {
        "timestamp": "2026-08-12T12:34:56",
        "config": {
            "models": models,
            "prompt": "prompt",
            "runs": 2,
            "delay_seconds": 0.5,
            "privacy_mode": False,
        },
        "results": {
            "model-a": {"source": successful},
            "model-b": {"source": failed},
        },
        "ranking": serialized_ranking,
    }
    assert data["config"]["models"] is models
    assert data["ranking"] is serialized_ranking
    assert list(successful_results) == ["model-a"]
    assert successful_results["model-a"] is successful
    assert events == [
        ("serialize", successful),
        ("serialize", failed),
        ("analyzer", None),
        ("rank", [successful]),
        ("serialize-ranking", ranking),
    ]


def test_build_benchmark_data_skips_analyzer_without_successes(monkeypatch):
    failed = SimpleNamespace(success=False)
    monkeypatch.setattr(
        mcp_benchmark,
        "_serialize_benchmark_result",
        lambda result, include_response_content: {
            "result": result,
            "include": include_response_content,
        },
    )

    def fail_if_called():
        raise AssertionError("analyzer must not be created")

    monkeypatch.setattr(mcp_benchmark, "ModelPerformanceAnalyzer", fail_if_called)

    data, successful_results = mcp_benchmark._build_benchmark_data(
        {"model-b": failed},
        timestamp="timestamp",
        models=[],
        prompt="prompt",
        runs=1,
        delay_seconds=0.0,
        include_prompts_in_logs=False,
    )

    assert "ranking" not in data
    assert data["results"]["model-b"] == {"result": failed, "include": False}
    assert successful_results == {}


@pytest.mark.asyncio
async def test_benchmark_models_delegates_data_building_and_keeps_save_boundary(
    monkeypatch,
):
    results = {"model-a": SimpleNamespace(success=True)}
    successful_results = {"model-a": results["model-a"]}
    benchmark_data = {"payload": "built"}
    handler = SimpleNamespace(
        benchmark_models=AsyncMock(return_value=results),
        save_results=AsyncMock(),
    )
    build_data = Mock(return_value=(benchmark_data, successful_results))

    class FrozenTimestamp:
        def __init__(self, value):
            self.value = value

        def isoformat(self):
            return self.value

        def strftime(self, format_string):
            assert format_string == "%Y%m%d_%H%M%S"
            return "20260812_123456"

    class FrozenDatetime:
        values = iter(
            [
                FrozenTimestamp("2026-08-12T12:34:55"),
                FrozenTimestamp("unused"),
            ]
        )

        @classmethod
        def now(cls):
            return next(cls.values)

    async def get_handler():
        return handler

    monkeypatch.setattr(mcp_benchmark, "get_benchmark_handler", get_handler)
    monkeypatch.setattr(mcp_benchmark, "_build_benchmark_data", build_data)
    monkeypatch.setattr(mcp_benchmark, "datetime", FrozenDatetime)

    response = await mcp_benchmark.benchmark_models(
        models=["model-a"],
        prompt="prompt",
        runs=2,
        delay_seconds=0.5,
        save_results=True,
        include_prompts_in_logs=False,
    )

    assert response is benchmark_data
    assert response["saved_file"] == "benchmark_20260812_123456.json"
    build_data.assert_called_once_with(
        results,
        timestamp="2026-08-12T12:34:55",
        models=["model-a"],
        prompt="prompt",
        runs=2,
        delay_seconds=0.5,
        include_prompts_in_logs=False,
    )
    handler.save_results.assert_awaited_once_with(
        results,
        "benchmark_20260812_123456.json",
    )
