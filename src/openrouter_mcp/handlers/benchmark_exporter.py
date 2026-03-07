#!/usr/bin/env python3
"""
Benchmark report exporting utilities.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List


class BenchmarkReportExporter:
    """Exports benchmark results to various formats."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def export_markdown(self, results: Dict[str, Any], output_path: str) -> str:
        """Export benchmark results to Markdown format."""

        # Support both BenchmarkResult (with error) and EnhancedBenchmarkResult (with success)
        def is_successful(r: Any) -> bool:
            if hasattr(r, "success"):
                return bool(r.success)
            return r.error is None if hasattr(r, "error") else True

        lines = [
            "# Benchmark Report",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- Models tested: {len(results)}",
            f"- Successful tests: {sum(1 for r in results.values() if is_successful(r))}",
            "",
            "## Results",
            "",
        ]

        for model_id, result in results.items():
            success = is_successful(result)
            lines.extend(
                [
                    f"### {model_id}",
                    "",
                    f"- **Success**: {'✅' if success else '❌'}",
                ]
            )

            # Add basic metrics for BenchmarkResult
            if success and hasattr(result, "response_time_ms"):
                lines.append(f"- **Response Time**: {result.response_time_ms:.2f}ms")
            if hasattr(result, "cost"):
                lines.append(f"- **Cost**: ${result.cost:.6f}")
            if hasattr(result, "tokens_used"):
                lines.append(f"- **Tokens Used**: {result.tokens_used}")

            # Add enhanced metrics if available
            if hasattr(result, "metrics") and result.metrics:
                if hasattr(result.metrics, "avg_response_time"):
                    lines.append(
                        f"- **Avg Response Time**: {result.metrics.avg_response_time:.2f}s"
                    )
                if hasattr(result.metrics, "avg_cost"):
                    lines.append(f"- **Avg Cost**: ${result.metrics.avg_cost:.6f}")
                if hasattr(result.metrics, "quality_score"):
                    lines.append(f"- **Quality Score**: {result.metrics.quality_score:.2f}")
                if hasattr(result.metrics, "throughput"):
                    lines.append(f"- **Throughput**: {result.metrics.throughput:.2f} tokens/s")

            if hasattr(result, "response") and result.response:
                preview = (
                    result.response[:200] + "..." if len(result.response) > 200 else result.response
                )
                lines.extend(
                    [
                        "",
                        "**Response Preview:**",
                        "```",
                        preview,
                        "```",
                    ]
                )

            lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self.logger.info(f"Markdown report exported to {output_path}")
        return output_path

    async def export_csv(self, results: Dict[str, Any], output_path: str) -> str:
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

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for model_id, result_list in results.items():
                # Handle both single results and lists of results
                result_entries: List[Any]
                if isinstance(result_list, list):
                    result_entries = result_list
                else:
                    result_entries = [result_list]

                for result in result_entries:
                    row = {
                        "model_id": model_id,
                        "success": (result.success if hasattr(result, "success") else True),
                        "response_time": (
                            result.response_time_ms if hasattr(result, "response_time_ms") else 0
                        ),
                        "cost": result.cost if hasattr(result, "cost") else 0,
                        "quality_score": 0,  # Not available in basic BenchmarkResult
                        "throughput": 0,  # Not available in basic BenchmarkResult
                        "tokens_used": (
                            result.tokens_used if hasattr(result, "tokens_used") else 0
                        ),
                        "response_length": (
                            len(result.response)
                            if hasattr(result, "response") and result.response
                            else 0
                        ),
                    }
                    writer.writerow(row)

        self.logger.info(f"CSV report exported to {output_path}")
        return output_path

    async def export_json(self, results: Dict[str, Any], output_path: str) -> str:
        """Export benchmark results to JSON format."""
        results_payload: Dict[str, Dict[str, Any]] = {}

        for model_id, result in results.items():
            # Support both BenchmarkResult and EnhancedBenchmarkResult
            success = (
                result.success
                if hasattr(result, "success")
                else (result.error is None if hasattr(result, "error") else True)
            )

            result_data = {
                "model_id": model_id,
                "success": success,
                "response": getattr(result, "response", None),
                "error_message": getattr(result, "error_message", getattr(result, "error", None)),
            }

            # Add basic metrics from BenchmarkResult
            if hasattr(result, "response_time_ms"):
                result_data["response_time_ms"] = result.response_time_ms
            if hasattr(result, "cost"):
                result_data["cost"] = result.cost
            if hasattr(result, "tokens_used"):
                result_data["tokens_used"] = result.tokens_used

            # Add enhanced metrics if available
            if hasattr(result, "metrics") and result.metrics:
                result_data["metrics"] = {
                    "avg_response_time": getattr(result.metrics, "avg_response_time", 0),
                    "avg_cost": getattr(result.metrics, "avg_cost", 0),
                    "quality_score": getattr(result.metrics, "quality_score", 0),
                    "throughput": getattr(result.metrics, "throughput", 0),
                    "avg_total_tokens": getattr(result.metrics, "avg_total_tokens", 0),
                    "success_rate": getattr(result.metrics, "success_rate", 1.0),
                }

            results_payload[model_id] = result_data

        export_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "results": results_payload,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"JSON report exported to {output_path}")
        return output_path
