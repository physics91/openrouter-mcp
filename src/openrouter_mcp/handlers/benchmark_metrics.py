"""Metric values shared by benchmark persistence and report exporters."""

import math
from collections.abc import Mapping
from typing import Any


def metric_value(metrics: Any, name: str, default: Any = None) -> Any:
    """Read both live metric objects and their serialized representation."""
    if isinstance(metrics, Mapping):
        return metrics.get(name, default)
    return getattr(metrics, name, default)


def nonnegative_measurement(value: Any) -> float | None:
    """Missing or invalid measurements must not masquerade as measured zeros."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def supplied_quality_score(metrics: Any) -> float | None:
    """Accept explicit supplied scores, excluding unmarked legacy heuristics.

    A live object's numeric score is supplied by its caller. Persisted numbers
    require the same provenance marker; it does not certify evaluator accuracy.
    """
    if isinstance(metrics, Mapping) and metrics.get("quality_evaluation") != "provided":
        return None
    value = nonnegative_measurement(metric_value(metrics, "quality_score"))
    return value if value is not None and value <= 1 else None


def validate_performance_weights(weights: Mapping[str, float]) -> None:
    """Reject invalid rankings before callers start benchmark requests."""
    if not weights or set(weights) - {"speed", "cost", "quality", "throughput"}:
        raise ValueError("Weights must name supported metrics and must not be empty")
    for value in weights.values():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError("Weights must be finite, nonnegative numbers")
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("Weights must have a finite, positive total")


def validate_benchmark_inputs(models: list[str], runs: int, delay: float) -> None:
    """Reject malformed or duplicate jobs before constructing a live handler."""
    if not models or any(
        not isinstance(model, str) or not model.strip() for model in models
    ):
        raise ValueError("models must contain nonempty model IDs")
    if len(models) != len(set(models)):
        raise ValueError("models must contain distinct model IDs")
    if type(runs) is not int or runs < 1:
        raise ValueError("runs must be a positive integer")
    if (
        isinstance(delay, bool)
        or not isinstance(delay, (int, float))
        or not math.isfinite(delay)
        or delay < 0
    ):
        raise ValueError("delay_seconds must be finite and nonnegative")
