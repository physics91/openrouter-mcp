from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.openrouter_mcp.handlers import mcp_benchmark


def test_group_category_benchmark_results_preserves_lookup_and_order():
    first_result = mcp_benchmark.EnhancedBenchmarkResult(
        model_id="shared-model",
        success=True,
        response="first response",
        error_message=None,
        metrics=None,
        timestamp=datetime.now(),
    )
    second_result = mcp_benchmark.EnhancedBenchmarkResult(
        model_id="second-model",
        success=True,
        response="second response",
        error_message=None,
        metrics=None,
        timestamp=datetime.now(),
    )
    unknown_result = mcp_benchmark.EnhancedBenchmarkResult(
        model_id="missing-model",
        success=True,
        response=None,
        error_message=None,
        metrics=None,
        timestamp=datetime.now(),
    )

    grouped = mcp_benchmark._group_category_benchmark_results(
        {
            "shared-model": first_result,
            "second-model": second_result,
            "missing-model": unknown_result,
        },
        [
            {"id": "shared-model", "category": "first-category"},
            {"id": "shared-model", "category": "second-category"},
            {"id": "second-model", "category": "first-category"},
        ],
    )

    assert grouped == {
        "first-category": [
            {
                "model_id": "shared-model",
                "success": True,
                "metrics": None,
                "response_length": len("first response"),
            },
            {
                "model_id": "second-model",
                "success": True,
                "metrics": None,
                "response_length": len("second response"),
            },
        ],
        "unknown": [
            {
                "model_id": "missing-model",
                "success": True,
                "metrics": None,
                "response_length": 0,
            }
        ],
    }


def test_group_models_by_category_preserves_order_identity_and_filtering():
    code_first = {"id": "code-first", "category": "code"}
    chat = {"id": "chat", "category": "chat"}
    unknown = {"id": "unknown"}
    code_second = {"id": "code-second", "category": "code"}
    models = [code_first, chat, unknown, code_second]

    grouped = mcp_benchmark._group_models_by_category(models, None)
    filtered = mcp_benchmark._group_models_by_category(models, ["chat", "code"])

    assert list(grouped) == ["code", "chat", "unknown"]
    assert grouped["code"][0] is code_first
    assert grouped["code"][1] is code_second
    assert grouped["chat"][0] is chat
    assert grouped["unknown"][0] is unknown
    assert list(filtered) == ["code", "chat"]
    assert filtered["code"][0] is code_first
    assert filtered["chat"][0] is chat


def test_select_top_category_models_preserves_stable_order_and_metric_calls(
    monkeypatch,
):
    code_first = {"id": "code-first"}
    code_second = {"id": "code-second"}
    chat = {"id": "chat"}
    score_calls = []

    def record_score(model, metric):
        score_calls.append((model["id"], metric))
        return 1.0

    monkeypatch.setattr(mcp_benchmark, "_selection_score", record_score)

    selected, category_info = mcp_benchmark._select_top_category_models(
        {
            "code": [code_first, code_second],
            "chat": [chat],
            "empty": [],
        },
        top_n=1,
        normalized_metric="speed",
    )

    assert selected == [code_first, chat]
    assert selected[0] is code_first
    assert score_calls == [
        ("code-first", "speed"),
        ("code-second", "speed"),
        ("chat", "speed"),
    ]
    assert category_info == {
        "code": {"total_models": 2, "selected_models": ["code-first"]},
        "chat": {"total_models": 1, "selected_models": ["chat"]},
    }


def test_select_top_category_models_zero_limit_keeps_category_info(monkeypatch):
    model = {"id": "chat-model"}
    score_calls = []
    monkeypatch.setattr(
        mcp_benchmark,
        "_selection_score",
        lambda candidate, metric: score_calls.append((candidate, metric)) or 1.0,
    )

    selected, category_info = mcp_benchmark._select_top_category_models(
        {"chat": [model]}, top_n=0, normalized_metric="overall"
    )

    assert selected == []
    assert score_calls == [(model, "overall")]
    assert category_info == {
        "chat": {"total_models": 1, "selected_models": []},
    }


@pytest.mark.asyncio
async def test_compare_model_categories_no_selection_preserves_exact_return(
    monkeypatch,
):
    cache = Mock()
    cache.get_models.return_value = [
        {"id": "chat-model", "category": "chat"},
        {"id": "code-model", "category": "code"},
    ]
    handler = SimpleNamespace(model_cache=cache, benchmark_models=AsyncMock())
    monkeypatch.setattr(
        mcp_benchmark,
        "get_benchmark_handler",
        AsyncMock(return_value=handler),
    )

    result = await mcp_benchmark.compare_model_categories(categories=["chat"], top_n=0)

    assert result == {
        "message": "비교할 모델이 없습니다.",
        "categories": ["chat"],
        "available_categories": ["chat"],
    }
    handler.benchmark_models.assert_not_called()
