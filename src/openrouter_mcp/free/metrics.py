"""Performance metrics for free model routing."""

from __future__ import annotations

from dataclasses import dataclass, field


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
