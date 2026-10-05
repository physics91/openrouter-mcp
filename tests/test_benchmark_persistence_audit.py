"""Local persistence regressions; no provider or model quality is simulated as real."""

import csv
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.openrouter_mcp.handlers.benchmark_exporter import BenchmarkReportExporter
from src.openrouter_mcp.handlers.mcp_benchmark import (
    _deserialize_benchmark_report_results,
    _get_best_model,
    _read_benchmark_files,
    compare_model_performance,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_basic_result_survives_export_and_report_reload(tmp_path):
    original = SimpleNamespace(
        success=True,
        response="Answer",
        response_time_ms=250,
        cost=0.01,
        tokens_used=30,
        throughput_tokens_per_second=120,
        quality_score=None,
    )
    path = tmp_path / "basic.json"
    await BenchmarkReportExporter().export_json({"model": original}, str(path))
    restored = _deserialize_benchmark_report_results(json.loads(path.read_text()))
    assert set(restored) == {"model"}
    assert restored["model"].metrics.avg_response_time == 0.25
    assert restored["model"].metrics.avg_cost == 0.01
    assert restored["model"].metrics.avg_total_tokens == 30
    assert restored["model"].metrics.throughput == 120


@pytest.mark.asyncio
async def test_measured_metrics_survive_json_reload_and_csv_export(tmp_path):
    original = SimpleNamespace(
        success=True,
        response="Measured answer",
        metrics=SimpleNamespace(
            avg_response_time=1.5,
            avg_cost=0.02,
            avg_total_tokens=42,
            throughput=28,
            success_rate=0.5,
            quality_score=None,
        ),
    )
    exporter = BenchmarkReportExporter()
    json_file = tmp_path / "report.json"
    await exporter.export_json({"model": original}, str(json_file))
    restored = _deserialize_benchmark_report_results(json.loads(json_file.read_text()))
    csv_file = tmp_path / "report.csv"
    await exporter.export_csv(restored, str(csv_file))
    with csv_file.open() as handle:
        row = next(csv.DictReader(handle))
    assert float(row["response_time"]) == 1500
    assert float(row["cost"]) == 0.02
    assert float(row["tokens_used"]) == 42
    assert float(row["throughput"]) == 28
    assert row["quality_score"] == ""
    assert restored["model"].metrics.success_rate == 0.5


@pytest.mark.parametrize("score", [0.99, 8, "0.9", float("nan"), float("inf")])
def test_legacy_or_invalid_quality_cannot_win_or_be_reexported(score):
    results = {"legacy": {"success": True, "metrics": {"quality_score": score}}}
    assert _get_best_model(results) is None
    restored = _deserialize_benchmark_report_results({"results": results})
    assert restored["legacy"].metrics.quality_score is None


def test_explicitly_provided_zero_quality_is_a_real_score():
    results = {
        "provided": {
            "success": True,
            "metrics": {"quality_score": 0, "quality_evaluation": "provided"},
        },
        "legacy": {"success": True, "metrics": {"quality_score": 0.99}},
    }
    assert _get_best_model(results) == "provided"


def test_history_limit_is_applied_after_model_filter_and_corrupt_files(tmp_path):
    for name, payload in {
        "older.json": {"results": {"wanted/model": {"success": True}}},
        "newer.json": {"results": {"different/model": {"success": True}}},
        "corrupt.json": {"results": ["wrong shape"]},
    }.items():
        (tmp_path / name).write_text(json.dumps(payload))
    times = {"older.json": 1, "newer.json": 2, "corrupt.json": 3}
    with patch(
        "src.openrouter_mcp.handlers.mcp_benchmark.os.path.getctime",
        side_effect=lambda path: times[path.rsplit("/", 1)[-1]],
    ):
        cutoff = (
            datetime.fromtimestamp(0, tz=timezone.utc).astimezone().replace(tzinfo=None)
        )
        history = _read_benchmark_files(str(tmp_path), cutoff, 1, "wanted")
    assert [entry["filename"] for entry in history] == ["older.json"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "weights",
    [
        {},
        {"speed": 0},
        {"speed": -1},
        {"speed": float("nan")},
        {"speed": float("inf")},
        {"unknown": 1},
    ],
)
async def test_invalid_weights_fail_before_creating_billable_handler(weights):
    from unittest.mock import AsyncMock

    from src.openrouter_mcp.handlers.benchmark import BenchmarkError

    with patch(
        "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler",
        new_callable=AsyncMock,
    ) as get_handler:
        with pytest.raises(BenchmarkError, match="weight|Weight"):
            await compare_model_performance(["model"], weights)
        get_handler.assert_not_awaited()
