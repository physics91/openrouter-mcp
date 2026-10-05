import csv
from types import SimpleNamespace
from unittest.mock import call, patch

import pytest

from src.openrouter_mcp.handlers import benchmark_exporter as exporter_module
from src.openrouter_mcp.handlers.benchmark_exporter import (
    BenchmarkReportExporter,
    _serialize_csv_result,
)

pytestmark = pytest.mark.unit


def test_serialize_csv_result_preserves_full_row_contract():
    result = SimpleNamespace(
        success=False,
        response_time_ms=12.5,
        cost=0.004,
        tokens_used=17,
        response="response",
    )

    serialized = _serialize_csv_result("model-full", result)

    assert list(serialized) == [
        "model_id",
        "success",
        "response_time",
        "cost",
        "quality_score",
        "throughput",
        "tokens_used",
        "response_length",
    ]
    assert serialized == {
        "model_id": "model-full",
        "success": False,
        "response_time": 12.5,
        "cost": 0.004,
        "quality_score": None,
        "throughput": None,
        "tokens_used": 17,
        "response_length": 8,
    }


def test_serialize_csv_result_preserves_sparse_defaults():
    assert _serialize_csv_result("model-sparse", SimpleNamespace()) == {
        "model_id": "model-sparse",
        "success": True,
        "response_time": None,
        "cost": None,
        "quality_score": None,
        "throughput": None,
        "tokens_used": None,
        "response_length": 0,
    }


@pytest.mark.parametrize("response", [None, "", [], 0, False])
def test_serialize_csv_result_keeps_falsey_response_length_at_zero(response):
    result = SimpleNamespace(response=response)

    serialized = _serialize_csv_result("model-falsey", result)

    assert serialized["response_length"] == 0


@pytest.mark.asyncio
async def test_export_csv_delegates_mixed_results_in_order(tmp_path):
    first = object()
    second = object()
    third = object()
    results = {
        "model-b": first,
        "model-a": [second, third],
        "model-empty": [],
    }
    output_path = tmp_path / "benchmark.csv"

    def serialize(model_id, result):
        return {
            "model_id": model_id,
            "success": result is not second,
            "response_time": 1,
            "cost": 2,
            "quality_score": None,
            "throughput": None,
            "tokens_used": 3,
            "response_length": 4,
        }

    exporter = BenchmarkReportExporter()
    with patch.object(
        exporter_module,
        "_serialize_csv_result",
        side_effect=serialize,
    ) as serialize_result, patch.object(exporter.logger, "info") as log:
        returned_path = await exporter.export_csv(results, str(output_path))

    with output_path.open(newline="", encoding="utf-8") as exported_file:
        reader = csv.DictReader(exported_file)
        rows = list(reader)

    assert returned_path == str(output_path)
    assert reader.fieldnames == [
        "model_id",
        "success",
        "response_time",
        "cost",
        "quality_score",
        "throughput",
        "tokens_used",
        "response_length",
    ]
    assert [row["model_id"] for row in rows] == ["model-b", "model-a", "model-a"]
    assert [row["success"] for row in rows] == ["True", "False", "True"]
    assert serialize_result.call_args_list == [
        call("model-b", first),
        call("model-a", second),
        call("model-a", third),
    ]
    log.assert_called_once_with(f"CSV report exported to {output_path}")


@pytest.mark.asyncio
async def test_export_csv_stops_after_serialization_failure(tmp_path):
    first = object()
    second = object()
    third = object()
    output_path = tmp_path / "benchmark.csv"
    first_row = {
        "model_id": "model",
        "success": True,
        "response_time": 1,
        "cost": 2,
        "quality_score": None,
        "throughput": None,
        "tokens_used": 3,
        "response_length": 4,
    }

    with patch.object(
        exporter_module,
        "_serialize_csv_result",
        side_effect=[first_row, RuntimeError("serialization failed")],
    ) as serialize_result, pytest.raises(RuntimeError, match="serialization failed"):
        await BenchmarkReportExporter().export_csv(
            {"model": [first, second, third]},
            str(output_path),
        )

    assert serialize_result.call_args_list == [
        call("model", first),
        call("model", second),
    ]
