"""Performance metrics for free model routing."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..config.constants import FreeChatConfig

logger = logging.getLogger(__name__)


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_latency_ms": self.total_latency_ms,
            "total_tokens": self.total_tokens,
            "error_counts": dict(self.error_counts),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelMetrics:
        m = cls(
            total_requests=data.get("total_requests", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            total_latency_ms=data.get("total_latency_ms", 0.0),
            total_tokens=data.get("total_tokens", 0),
        )
        m.error_counts = defaultdict(int, data.get("error_counts", {}))
        return m


class MetricsCollector:
    """Collects and aggregates performance metrics for free models.

    Safe under single-threaded asyncio usage (no cross-thread guarantees).
    Aggregates success/failure records with a weighted performance score
    combining success rate, latency, and throughput.
    """

    def __init__(self, persistence_path: Optional[str] = None) -> None:
        self._metrics: Dict[str, ModelMetrics] = {}
        self._persistence_path = persistence_path
        self._record_count_since_save = 0
        if persistence_path:
            self._load()

    def _load(self) -> None:
        """Load metrics from disk. Corrupted files are logged and ignored."""
        if not self._persistence_path or not os.path.exists(self._persistence_path):
            return
        try:
            with open(self._persistence_path) as f:
                data = json.load(f)
            for model_id, model_data in data.items():
                self._metrics[model_id] = ModelMetrics.from_dict(model_data)
        except (json.JSONDecodeError, OSError, TypeError, KeyError) as e:
            logger.warning(
                "메트릭 캐시 파일이 손상되었습니다. 빈 상태로 시작합니다: %s", e
            )

    def save(self) -> None:
        """Persist metrics to disk using atomic write (tmp → rename)."""
        if not self._persistence_path:
            return
        dir_path = os.path.dirname(self._persistence_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        data = {mid: m.to_dict() for mid, m in self._metrics.items()}
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=dir_path or ".", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f)
                os.replace(tmp_path, self._persistence_path)
            except BaseException:
                os.unlink(tmp_path)
                raise
        except OSError as e:
            logger.warning("메트릭 저장 실패: %s", e)

    def _maybe_auto_save(self) -> None:
        """Auto-save every N records."""
        self._record_count_since_save += 1
        if (
            self._persistence_path
            and self._record_count_since_save >= FreeChatConfig.METRICS_SAVE_INTERVAL
        ):
            self.save()
            self._record_count_since_save = 0

    def record_success(
        self, model_id: str, latency_ms: float, tokens_used: int
    ) -> None:
        """Record a successful request for *model_id*."""
        m = self._metrics.setdefault(model_id, ModelMetrics())
        m.total_requests += 1
        m.success_count += 1
        m.total_latency_ms += latency_ms
        m.total_tokens += tokens_used
        self._maybe_auto_save()

    def record_failure(self, model_id: str, error_type: str) -> None:
        """Record a failed request for *model_id*."""
        m = self._metrics.setdefault(model_id, ModelMetrics())
        m.total_requests += 1
        m.failure_count += 1
        m.error_counts[error_type] += 1
        self._maybe_auto_save()

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

        latency_score = 1.0 - min(m.avg_latency_ms / FreeChatConfig.MAX_LATENCY_MS, 1.0)
        throughput_score = min(
            m.tokens_per_second / FreeChatConfig.MAX_TOKENS_PER_SECOND, 1.0
        )

        return (
            FreeChatConfig.PERFORMANCE_SUCCESS_WEIGHT * m.success_rate
            + FreeChatConfig.PERFORMANCE_LATENCY_WEIGHT * latency_score
            + FreeChatConfig.PERFORMANCE_THROUGHPUT_WEIGHT * throughput_score
        )
