import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openrouter_mcp.handlers import mcp_benchmark as benchmark_module

pytestmark = pytest.mark.unit


class _ExplodingItems:
    def __init__(self, error):
        self.error = error

    def items(self):
        raise self.error


class _ExplodingGet:
    def __init__(self, error):
        self.error = error

    def get(self, *_args, **_kwargs):
        raise self.error


def test_deserialize_benchmark_report_results_filters_and_converts_in_order():
    data = {
        "results": {
            "model-a": {
                "success": "yes",
                "response": "first",
                "metrics": {
                    "avg_response_time": "1.5",
                    "avg_cost": "0.002",
                    "quality_score": "8",
                    "throughput": "120",
                },
            },
            "failed-model": {
                "success": False,
                "metrics": {"quality_score": 10},
            },
            "missing-metrics": {"success": True, "metrics": {}},
            "model-b": {
                "success": True,
                "metrics": {
                    "avg_response_time": None,
                    "avg_cost": "invalid",
                },
            },
        }
    }

    results = benchmark_module._deserialize_benchmark_report_results(data)

    assert list(results) == ["model-a", "model-b"]
    assert results["model-a"] == benchmark_module.ReportResult(
        model_id="model-a",
        success=True,
        response="first",
        metrics=benchmark_module.ReportMetrics(
            avg_response_time=1.5,
            avg_cost=0.002,
            quality_score=None,
            throughput=120.0,
        ),
    )
    assert results["model-b"] == benchmark_module.ReportResult(
        model_id="model-b",
        success=True,
        response="",
        metrics=benchmark_module.ReportMetrics(),
    )


@pytest.mark.parametrize(
    "data_factory",
    [
        lambda error: {"results": _ExplodingItems(error)},
        lambda error: {"results": {"model-a": _ExplodingGet(error)}},
        lambda error: {
            "results": {
                "model-a": {
                    "success": True,
                    "metrics": _ExplodingGet(error),
                }
            }
        },
    ],
)
def test_deserialize_benchmark_report_results_propagates_malformed_shape_errors(
    data_factory,
):
    error = RuntimeError("malformed payload")

    with pytest.raises(RuntimeError) as raised:
        benchmark_module._deserialize_benchmark_report_results(data_factory(error))

    assert raised.value is error


@pytest.mark.asyncio
async def test_export_benchmark_report_delegates_loaded_payload_and_result_identity(
    tmp_path,
):
    benchmark_file = "benchmark.json"
    input_path = tmp_path / benchmark_file
    input_path.write_text(json.dumps({"source": "payload"}), encoding="utf-8")
    results = {
        "model-b": benchmark_module.ReportResult("model-b", True, "second"),
        "model-a": benchmark_module.ReportResult("model-a", True, "first"),
    }
    handler = MagicMock(results_dir=str(tmp_path))
    exporter = AsyncMock()

    with patch.object(
        benchmark_module,
        "get_benchmark_handler",
        return_value=handler,
    ), patch.object(
        benchmark_module,
        "_deserialize_benchmark_report_results",
        return_value=results,
    ) as deserialize, patch.object(
        benchmark_module,
        "BenchmarkReportExporter",
        return_value=exporter,
    ):
        response = await benchmark_module.export_benchmark_report(
            benchmark_file,
            format="json",
        )

    deserialize.assert_called_once_with({"source": "payload"})
    exporter.export_json.assert_awaited_once_with(
        results,
        str(tmp_path / "benchmark_report.json"),
    )
    assert response["models_included"] == ["model-b", "model-a"]
