import json
from types import SimpleNamespace
from unittest.mock import call, patch

import pytest

from src.openrouter_mcp.handlers import benchmark_exporter as exporter_module
from src.openrouter_mcp.handlers.benchmark_exporter import (
    BenchmarkReportExporter,
    _serialize_json_result,
)

pytestmark = pytest.mark.unit


def test_serialize_json_result_preserves_basic_result_contract():
    result = SimpleNamespace(
        success=False,
        response="partial response",
        error_message="request failed",
        error="legacy error",
        response_time_ms=12.5,
        cost=0.004,
        tokens_used=17,
    )

    serialized = _serialize_json_result("model-basic", result)

    assert list(serialized) == [
        "model_id",
        "success",
        "response",
        "error_message",
        "response_time_ms",
        "cost",
        "tokens_used",
    ]
    assert serialized == {
        "model_id": "model-basic",
        "success": False,
        "response": "partial response",
        "error_message": "request failed",
        "response_time_ms": 12.5,
        "cost": 0.004,
        "tokens_used": 17,
    }


def test_serialize_json_result_preserves_enhanced_metric_defaults():
    metrics = SimpleNamespace(avg_response_time=1.25, quality_score=0.91)
    response = object()
    result = SimpleNamespace(
        success=True,
        response=response,
        error=None,
        metrics=metrics,
    )

    serialized = _serialize_json_result("model-enhanced", result)

    assert serialized["response"] is response
    assert serialized == {
        "model_id": "model-enhanced",
        "success": True,
        "response": response,
        "error_message": None,
        "metrics": {
            "avg_response_time": 1.25,
            "avg_cost": 0,
            "quality_score": 0.91,
            "throughput": 0,
            "avg_total_tokens": 0,
            "success_rate": 1.0,
        },
    }


@pytest.mark.parametrize(
    ("result", "expected_success", "expected_error"),
    [
        (SimpleNamespace(error="legacy failure"), False, "legacy failure"),
        (SimpleNamespace(), True, None),
    ],
)
def test_serialize_json_result_preserves_sparse_error_fallbacks(
    result, expected_success, expected_error
):
    serialized = _serialize_json_result("model-sparse", result)

    assert serialized == {
        "model_id": "model-sparse",
        "success": expected_success,
        "response": None,
        "error_message": expected_error,
    }


def test_serialize_json_result_preserves_eager_error_fallback_exception():
    class Result:
        success = True
        response = "response"
        error_message = None

        @property
        def error(self):
            raise RuntimeError("error fallback accessed")

    with pytest.raises(RuntimeError, match="error fallback accessed"):
        _serialize_json_result("model-eager", Result())


@pytest.mark.asyncio
async def test_export_json_delegates_in_order_and_preserves_file_contract(tmp_path):
    events = []
    first = object()
    second = object()
    results = {"model-b": first, "model-a": second}
    output_path = tmp_path / "benchmark.json"

    def serialize(model_id, result):
        events.append(f"serialize:{model_id}")
        expected_result = first if model_id == "model-b" else second
        assert result is expected_result
        return {"model_id": model_id, "label": "한국어"}

    class FrozenTimestamp:
        def isoformat(self):
            events.append("isoformat")
            return "2026-08-12T12:34:56"

    class FrozenDatetime:
        @classmethod
        def now(cls):
            events.append("now")
            return FrozenTimestamp()

    exporter = BenchmarkReportExporter()
    with patch.object(
        exporter_module,
        "_serialize_json_result",
        side_effect=serialize,
    ) as serialize_result, patch.object(
        exporter_module,
        "datetime",
        FrozenDatetime,
    ), patch.object(
        exporter.logger,
        "info",
        side_effect=lambda message: events.append(f"log:{message}"),
    ) as log:
        returned_path = await exporter.export_json(results, str(output_path))

    expected_payload = {
        "timestamp": "2026-08-12T12:34:56",
        "results": {
            "model-b": {"model_id": "model-b", "label": "한국어"},
            "model-a": {"model_id": "model-a", "label": "한국어"},
        },
    }
    assert returned_path == str(output_path)
    assert output_path.read_text(encoding="utf-8") == json.dumps(
        expected_payload,
        indent=2,
        ensure_ascii=False,
    )
    assert serialize_result.call_args_list == [
        call("model-b", first),
        call("model-a", second),
    ]
    log.assert_called_once_with(f"JSON report exported to {output_path}")
    assert events == [
        "serialize:model-b",
        "serialize:model-a",
        "now",
        "isoformat",
        f"log:JSON report exported to {output_path}",
    ]
