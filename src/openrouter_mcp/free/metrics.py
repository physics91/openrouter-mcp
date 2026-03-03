"""Performance metrics for free model routing."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional

from ..config.constants import FreeChatConfig


@dataclass
class ModelMetrics:
    """Tracks performance metrics for a single free model.

    All fields default to zero for safe initialization.
    Computed properties handle zero-division gracefully.
    """

    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def success_rate(self) -> float:
        """Fraction of successful requests (0.0 when no requests)."""
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """Average latency per successful request (0.0 when no successes)."""
        if self.success_count == 0:
            return 0.0
        return self.total_latency_ms / self.success_count

    @property
    def tokens_per_second(self) -> float:
        """Throughput in tokens/second (0.0 when no latency or no tokens)."""
        if self.total_latency_ms == 0.0 or self.total_tokens == 0:
            return 0.0
        return self.total_tokens / (self.total_latency_ms / 1000.0)


class MetricsCollector:
    """Collects and aggregates performance metrics for free models.

    Safe under single-threaded asyncio usage (no cross-thread guarantees).
    Aggregates success/failure records with a weighted performance score
    combining success rate, latency, and throughput.
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, ModelMetrics] = {}

    def record_success(
        self, model_id: str, latency_ms: float, tokens_used: int
    ) -> None:
        """Record a successful request for *model_id*."""
        m = self._metrics.setdefault(model_id, ModelMetrics())
        m.total_requests += 1
        m.success_count += 1
        m.total_latency_ms += latency_ms
        m.total_tokens += tokens_used

    def record_failure(self, model_id: str, error_type: str) -> None:
        """Record a failed request for *model_id*."""
        m = self._metrics.setdefault(model_id, ModelMetrics())
        m.total_requests += 1
        m.failure_count += 1
        m.error_counts[error_type] += 1

    def get_metrics(self, model_id: str) -> Optional[ModelMetrics]:
        """Return metrics for *model_id*, or ``None`` if unknown."""
        return self._metrics.get(model_id)

    def get_all_metrics(self) -> Dict[str, ModelMetrics]:
        """Return a shallow copy of all collected metrics."""
        return dict(self._metrics)

    def get_performance_score(self, model_id: str) -> float:
        """Compute a weighted performance score in [0.0, 1.0].

        score = W_s * success_rate + W_l * latency_score + W_t * throughput_score

        where:
            latency_score   = 1.0 - min(avg_latency_ms / MAX_LATENCY_MS, 1.0)
            throughput_score = min(tokens_per_second / MAX_TOKENS_PER_SECOND, 1.0)
        """
        m = self._metrics.get(model_id)
        if m is None:
            return 0.0

        latency_score = 1.0 - min(
            m.avg_latency_ms / FreeChatConfig.MAX_LATENCY_MS, 1.0
        )
        throughput_score = min(
            m.tokens_per_second / FreeChatConfig.MAX_TOKENS_PER_SECOND, 1.0
        )

        return (
            FreeChatConfig.PERFORMANCE_SUCCESS_WEIGHT * m.success_rate
            + FreeChatConfig.PERFORMANCE_LATENCY_WEIGHT * latency_score
            + FreeChatConfig.PERFORMANCE_THROUGHPUT_WEIGHT * throughput_score
        )
