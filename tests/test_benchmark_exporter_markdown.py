from datetime import datetime
from types import SimpleNamespace

import pytest

from src.openrouter_mcp.handlers import benchmark_exporter
from src.openrouter_mcp.handlers.benchmark_exporter import BenchmarkReportExporter


@pytest.mark.asyncio
async def test_export_markdown_preserves_exact_output_and_success_precedence(
    tmp_path, monkeypatch
):
    frozen_now = datetime(2026, 8, 12, 17, 45, 30)
    monkeypatch.setattr(
        benchmark_exporter,
        "datetime",
        SimpleNamespace(now=lambda: frozen_now),
    )

    long_response = "x" * 201
    results = {
        "enhanced-model": SimpleNamespace(
            success=True,
            error="ignored because success is present",
            response_time_ms=123.45,
            cost=0.001234,
            tokens_used=42,
            metrics=SimpleNamespace(
                avg_response_time=1.23,
                avg_cost=0.000456,
                quality_score=0.87,
                throughput=12.34,
            ),
            response=long_response,
        ),
        "failed-model": SimpleNamespace(
            success=False,
            error=None,
            response_time_ms=44.0,
            cost=0.5,
            tokens_used=7,
            response="failed response",
        ),
        "implicit-success-model": SimpleNamespace(),
    }
    output_path = tmp_path / "report.md"

    returned_path = await BenchmarkReportExporter().export_markdown(
        results, str(output_path)
    )

    expected = "\n".join(
        [
            "# Benchmark Report",
            "Generated on: 2026-08-12 17:45:30",
            "",
            "## Summary",
            "- Models tested: 3",
            "- Successful tests: 2",
            "",
            "## Results",
            "",
            "### enhanced-model",
            "",
            "- **Success**: ✅",
            "- **Response Time**: 123.45ms",
            "- **Cost**: $0.001234",
            "- **Tokens Used**: 42",
            "- **Avg Response Time**: 1.23s",
            "- **Avg Cost**: $0.000456",
            "- **Quality Score**: 0.87",
            "- **Throughput**: 12.34 tokens/s",
            "",
            "**Response Preview:**",
            "```",
            "x" * 200 + "...",
            "```",
            "",
            "### failed-model",
            "",
            "- **Success**: ❌",
            "- **Cost**: $0.500000",
            "- **Tokens Used**: 7",
            "",
            "**Response Preview:**",
            "```",
            "failed response",
            "```",
            "",
            "### implicit-success-model",
            "",
            "- **Success**: ✅",
            "",
        ]
    )

    assert returned_path == str(output_path)
    assert output_path.read_text(encoding="utf-8") == expected
