import csv
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.handlers.benchmark import (
    BenchmarkError,
    BenchmarkReportExporter,
    BenchmarkResult,
    EnhancedBenchmarkMetrics,
    EnhancedBenchmarkResult,
    ModelPerformanceAnalyzer,
    ResponseQualityAnalyzer,
)
from src.openrouter_mcp.handlers.mcp_benchmark import (
    _analyze_cost_efficiency,
    _deserialize_benchmark_report_results,
    compare_model_categories,
    compare_model_performance,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("answer", ["Paris.", "The capital of France is Berlin. " * 15])
def test_surface_features_do_not_claim_to_measure_correctness(answer):
    analysis = ResponseQualityAnalyzer().analyze_response(
        "What is the capital of France?", answer
    )
    assert analysis["quality_score"] is None
    assert analysis["quality_evaluation"] == "not_evaluated"
    assert 0 <= analysis["text_heuristic_score"] <= 1


def test_unknown_quality_survives_aggregation_and_cannot_win_quality_ranking():
    sample = BenchmarkResult(
        model_id="evaluation/model",
        prompt="Question",
        response="Answer",
        response_time_ms=100,
        tokens_used=10,
        cost=0.01,
        timestamp=datetime.now(timezone.utc),
    )
    metrics = EnhancedBenchmarkMetrics.from_benchmark_results([sample])
    assert metrics.quality_score is None
    result = EnhancedBenchmarkResult(
        model_id=sample.model_id,
        success=True,
        response=sample.response,
        error_message=None,
        metrics=metrics,
        timestamp=datetime.now(timezone.utc),
    )
    analyzer = ModelPerformanceAnalyzer()
    comparison = analyzer.compare_models([result])
    assert comparison["averages"]["quality_score"] is None
    assert "quality" not in comparison["best_performers"]
    with pytest.raises(ValueError, match="[Qq]uality"):
        analyzer.rank_models_with_weights([result], {"quality": 1.0})


@pytest.mark.asyncio
async def test_quality_comparisons_reject_before_initializing_billable_work(
    monkeypatch,
):
    handler_factory = AsyncMock()
    monkeypatch.setattr(
        "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler",
        handler_factory,
    )
    with pytest.raises(BenchmarkError, match="[Qq]uality"):
        await compare_model_performance(["evaluation/model"], {"quality": 1.0})
    with pytest.raises(BenchmarkError, match="[Qq]uality"):
        await compare_model_categories(metric="quality")
    handler_factory.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_quality_survives_export_and_report_round_trip(tmp_path):
    result = EnhancedBenchmarkResult(
        model_id="evaluation/model",
        success=True,
        response="Paris.",
        error_message=None,
        metrics=EnhancedBenchmarkMetrics(avg_response_time=0.1, avg_cost=0.01),
        timestamp=datetime.now(timezone.utc),
    )
    results = {result.model_id: result}
    exporter = BenchmarkReportExporter()
    json_path = tmp_path / "report.json"
    await exporter.export_json(results, str(json_path))
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["results"][result.model_id]["metrics"]["quality_score"] is None

    restored = _deserialize_benchmark_report_results(payload)
    assert restored[result.model_id].metrics.quality_score is None
    assert _analyze_cost_efficiency(restored) == {}

    markdown_path = tmp_path / "report.md"
    await exporter.export_markdown(restored, str(markdown_path))
    assert "**Quality Score**: Not evaluated" in markdown_path.read_text(
        encoding="utf-8"
    )
    csv_path = tmp_path / "report.csv"
    await exporter.export_csv(restored, str(csv_path))
    with csv_path.open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["quality_score"] == ""
