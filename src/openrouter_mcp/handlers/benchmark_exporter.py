#!/usr/bin/env python3
"""
Benchmark report exporting utilities.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, TextIO

from ..utils._atomic_file import replace_file_atomically
from .benchmark_metrics import metric_value, supplied_quality_score


def _success_value(result: Any) -> Any:
    """Return the raw success value supported by both result variants."""
    if hasattr(result, "success"):
        return result.success
    return result.error is None if hasattr(result, "error") else True


def _is_successful(result: Any) -> bool:
    """Return the boolean success state used by rendered reports."""
    return bool(_success_value(result))


def _render_basic_markdown_metrics(result: Any, success: bool) -> list[str]:
    """Render metrics exposed by the basic benchmark result."""
    lines = []
    if success and hasattr(result, "response_time_ms"):
        lines.append(f"- **Response Time**: {result.response_time_ms:.2f}ms")
    if hasattr(result, "cost"):
        lines.append(f"- **Cost**: ${result.cost:.6f}")
    if hasattr(result, "tokens_used"):
        lines.append(f"- **Tokens Used**: {result.tokens_used}")
    return lines


def _render_enhanced_markdown_metrics(result: Any) -> list[str]:
    """Render metrics exposed by the enhanced benchmark result."""
    lines = []
    if hasattr(result, "metrics") and result.metrics:
        latency = metric_value(result.metrics, "avg_response_time")
        cost = metric_value(result.metrics, "avg_cost")
        throughput = metric_value(result.metrics, "throughput")
        if latency is not None:
            lines.append(f"- **Avg Response Time**: {latency:.2f}s")
        if cost is not None:
            lines.append(f"- **Avg Cost**: ${cost:.6f}")
        if metric_value(result.metrics, "quality_score", "absent") != "absent":
            quality = supplied_quality_score(result.metrics)
            rendered = f"{quality:.2f}" if quality is not None else "Not evaluated"
            lines.append(f"- **Quality Score**: {rendered}")
        if throughput is not None:
            lines.append(f"- **Throughput**: {throughput:.2f} tokens/s")
    return lines


def _render_response_preview(result: Any) -> list[str]:
    """Render the optional response preview block."""
    if not (hasattr(result, "response") and result.response):
        return []

    preview = (
        result.response[:200] + "..." if len(result.response) > 200 else result.response
    )
    return ["", "**Response Preview:**", "```", preview, "```"]


def _render_markdown_result(model_id: str, result: Any) -> list[str]:
    """Render one benchmark result section."""
    success = _is_successful(result)
    lines = [
        f"### {model_id}",
        "",
        f"- **Success**: {'✅' if success else '❌'}",
    ]
    lines.extend(_render_basic_markdown_metrics(result, success))
    lines.extend(_render_enhanced_markdown_metrics(result))
    lines.extend(_render_response_preview(result))
    lines.append("")
    return lines


def _serialize_json_result(model_id: str, result: Any) -> dict[str, Any]:
    """Serialize one benchmark result for JSON export."""
    success = _success_value(result)

    result_data = {
        "model_id": model_id,
        "success": success,
        "response": getattr(result, "response", None),
        "error_message": getattr(
            result, "error_message", getattr(result, "error", None)
        ),
    }

    if hasattr(result, "response_time_ms"):
        result_data["response_time_ms"] = result.response_time_ms
    if hasattr(result, "cost"):
        result_data["cost"] = result.cost
    if hasattr(result, "tokens_used"):
        result_data["tokens_used"] = result.tokens_used
    if hasattr(result, "throughput_tokens_per_second"):
        result_data["throughput_tokens_per_second"] = (
            result.throughput_tokens_per_second
        )
    if hasattr(result, "quality_score"):
        quality = supplied_quality_score(result)
        result_data["quality_score"] = quality
        result_data["quality_evaluation"] = (
            "provided" if quality is not None else "not_evaluated"
        )

    if hasattr(result, "metrics") and result.metrics:
        quality = supplied_quality_score(result.metrics)
        result_data["metrics"] = {
            "avg_response_time": metric_value(result.metrics, "avg_response_time"),
            "avg_cost": metric_value(result.metrics, "avg_cost"),
            "quality_score": quality,
            "quality_evaluation": (
                "provided" if quality is not None else "not_evaluated"
            ),
            "throughput": metric_value(result.metrics, "throughput"),
            "avg_total_tokens": metric_value(result.metrics, "avg_total_tokens"),
            "success_rate": metric_value(result.metrics, "success_rate"),
        }

    return result_data


def _serialize_csv_result(model_id: str, result: Any) -> dict[str, Any]:
    """Serialize a CSV row with latency in milliseconds for both result types."""
    metrics = getattr(result, "metrics", None)
    latency = metric_value(metrics, "avg_response_time")
    return {
        "model_id": model_id,
        "success": _success_value(result),
        "response_time": (
            latency * 1000
            if latency is not None
            else getattr(result, "response_time_ms", None)
        ),
        "cost": metric_value(metrics, "avg_cost", getattr(result, "cost", None)),
        "quality_score": supplied_quality_score(
            metrics if metrics is not None else result
        ),
        "throughput": metric_value(
            metrics, "throughput", getattr(result, "throughput_tokens_per_second", None)
        ),
        "tokens_used": metric_value(
            metrics, "avg_total_tokens", getattr(result, "tokens_used", None)
        ),
        "response_length": (
            len(result.response)
            if hasattr(result, "response") and result.response
            else 0
        ),
    }


class BenchmarkReportExporter:
    """Exports benchmark results to various formats."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def export_markdown(self, results: dict[str, Any], output_path: str) -> str:
        """Export benchmark results to Markdown format."""
        lines = [
            "# Benchmark Report",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- Models tested: {len(results)}",
            f"- Successful tests: {sum(1 for r in results.values() if _is_successful(r))}",
            "",
            "## Results",
            "",
        ]

        for model_id, result in results.items():
            lines.extend(_render_markdown_result(model_id, result))

        def write_markdown(handle: TextIO) -> None:
            handle.write("\n".join(lines))

        replace_file_atomically(
            output_path,
            os.path.dirname(output_path),
            write_markdown,
            encoding="utf-8",
        )

        self.logger.info(f"Markdown report exported to {output_path}")
        return output_path

    async def export_csv(self, results: dict[str, Any], output_path: str) -> str:
        """Export benchmark results to CSV format."""
        import csv

        fieldnames = [
            "model_id",
            "success",
            "response_time",
            "cost",
            "quality_score",
            "throughput",
            "tokens_used",
            "response_length",
        ]

        def write_csv(handle: TextIO) -> None:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()

            for model_id, result_list in results.items():
                # Handle both single results and lists of results
                result_entries: list[Any]
                if isinstance(result_list, list):
                    result_entries = result_list
                else:
                    result_entries = [result_list]

                for result in result_entries:
                    writer.writerow(_serialize_csv_result(model_id, result))

        replace_file_atomically(
            output_path,
            os.path.dirname(output_path),
            write_csv,
            encoding="utf-8",
            newline="",
        )

        self.logger.info(f"CSV report exported to {output_path}")
        return output_path

    async def export_json(self, results: dict[str, Any], output_path: str) -> str:
        """Export benchmark results to JSON format."""
        results_payload: dict[str, dict[str, Any]] = {}

        for model_id, result in results.items():
            results_payload[model_id] = _serialize_json_result(model_id, result)

        export_data: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "results": results_payload,
        }

        replace_file_atomically(
            output_path,
            os.path.dirname(output_path),
            lambda handle: json.dump(export_data, handle, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self.logger.info(f"JSON report exported to {output_path}")
        return output_path
