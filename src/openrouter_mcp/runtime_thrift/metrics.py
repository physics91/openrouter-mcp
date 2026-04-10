"""Shared thrift metrics for token-saving runtime optimizations."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from threading import Lock
from typing import Any, Callable, Dict, Iterator, Optional

from ..config.constants import CacheConfig, PricingDefaults
from ..utils.metadata import extract_provider_from_id

logger = logging.getLogger(__name__)
_PERSISTENCE_VERSION = 1


@dataclass
class CacheEfficiencyBucket:
    """Observed request and prompt-cache counters for a single provider/model bucket."""

    observed_requests: int = 0
    cached_prompt_tokens: int = 0
    cache_write_prompt_tokens: int = 0
    cache_hit_requests: int = 0
    cache_write_requests: int = 0
    saved_cost_usd: float = 0.0


@dataclass
class ThriftMetrics:
    """Aggregate counters for thrift optimizations."""

    coalesced_requests: int = 0
    recent_reuse_requests: int = 0
    recent_reuse_prompt_tokens: int = 0
    recent_reuse_completion_tokens: int = 0
    saved_prompt_tokens: int = 0
    saved_completion_tokens: int = 0
    saved_cost_usd: float = 0.0
    compacted_tokens: int = 0
    deferred_requests: int = 0
    cached_prompt_tokens: int = 0
    cache_write_prompt_tokens: int = 0
    cache_hit_requests: int = 0
    cache_write_requests: int = 0
    cache_efficiency_by_provider: Dict[str, CacheEfficiencyBucket] = field(default_factory=dict)
    cache_efficiency_by_model: Dict[str, CacheEfficiencyBucket] = field(default_factory=dict)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _snapshot_cache_bucket(bucket: CacheEfficiencyBucket) -> Dict[str, Any]:
    snapshot = asdict(bucket)
    snapshot["saved_cost_usd"] = round(float(snapshot["saved_cost_usd"]), 8)
    return snapshot


def _normalize_model_key(model: str | None) -> str | None:
    if not isinstance(model, str):
        return None
    normalized = model.strip()
    return normalized or None


def _get_cache_bucket(
    bucket_map: Dict[str, CacheEfficiencyBucket],
    key: str,
) -> CacheEfficiencyBucket:
    bucket = bucket_map.get(key)
    if bucket is None:
        bucket = CacheEfficiencyBucket()
        bucket_map[key] = bucket
    return bucket


def _iter_cache_buckets_for_model(
    metrics: ThriftMetrics,
    model: str | None,
) -> Iterator[CacheEfficiencyBucket]:
    model_key = _normalize_model_key(model)
    if model_key is None:
        return
    provider_key = extract_provider_from_id(model_key).value
    yield _get_cache_bucket(metrics.cache_efficiency_by_provider, provider_key)
    yield _get_cache_bucket(metrics.cache_efficiency_by_model, model_key)


def _snapshot_from_metrics(metrics: ThriftMetrics) -> Dict[str, Any]:
    snapshot = asdict(metrics)
    snapshot["saved_cost_usd"] = round(float(snapshot["saved_cost_usd"]), 8)
    snapshot["cache_efficiency_by_provider"] = {
        key: _snapshot_cache_bucket(bucket)
        for key, bucket in metrics.cache_efficiency_by_provider.items()
    }
    snapshot["cache_efficiency_by_model"] = {
        key: _snapshot_cache_bucket(bucket)
        for key, bucket in metrics.cache_efficiency_by_model.items()
    }
    return snapshot


def _cache_bucket_from_snapshot(snapshot: Dict[str, Any]) -> CacheEfficiencyBucket:
    return CacheEfficiencyBucket(
        observed_requests=_as_int(snapshot.get("observed_requests")),
        cached_prompt_tokens=_as_int(snapshot.get("cached_prompt_tokens")),
        cache_write_prompt_tokens=_as_int(snapshot.get("cache_write_prompt_tokens")),
        cache_hit_requests=_as_int(snapshot.get("cache_hit_requests")),
        cache_write_requests=_as_int(snapshot.get("cache_write_requests")),
        saved_cost_usd=_as_float(snapshot.get("saved_cost_usd")),
    )


def _metrics_from_snapshot(snapshot: Dict[str, Any]) -> ThriftMetrics:
    metrics = ThriftMetrics(
        coalesced_requests=_as_int(snapshot.get("coalesced_requests")),
        recent_reuse_requests=_as_int(snapshot.get("recent_reuse_requests")),
        recent_reuse_prompt_tokens=_as_int(snapshot.get("recent_reuse_prompt_tokens")),
        recent_reuse_completion_tokens=_as_int(snapshot.get("recent_reuse_completion_tokens")),
        saved_prompt_tokens=_as_int(snapshot.get("saved_prompt_tokens")),
        saved_completion_tokens=_as_int(snapshot.get("saved_completion_tokens")),
        saved_cost_usd=_as_float(snapshot.get("saved_cost_usd")),
        compacted_tokens=_as_int(snapshot.get("compacted_tokens")),
        deferred_requests=_as_int(snapshot.get("deferred_requests")),
        cached_prompt_tokens=_as_int(snapshot.get("cached_prompt_tokens")),
        cache_write_prompt_tokens=_as_int(snapshot.get("cache_write_prompt_tokens")),
        cache_hit_requests=_as_int(snapshot.get("cache_hit_requests")),
        cache_write_requests=_as_int(snapshot.get("cache_write_requests")),
    )
    provider_breakdown = snapshot.get("cache_efficiency_by_provider")
    if isinstance(provider_breakdown, dict):
        metrics.cache_efficiency_by_provider = {
            str(key): _cache_bucket_from_snapshot(bucket)
            for key, bucket in provider_breakdown.items()
            if isinstance(bucket, dict)
        }
    model_breakdown = snapshot.get("cache_efficiency_by_model")
    if isinstance(model_breakdown, dict):
        metrics.cache_efficiency_by_model = {
            str(key): _cache_bucket_from_snapshot(bucket)
            for key, bucket in model_breakdown.items()
            if isinstance(bucket, dict)
        }
    return metrics


def _merge_cache_bucket_into(
    target: CacheEfficiencyBucket,
    source: CacheEfficiencyBucket,
) -> None:
    target.observed_requests += source.observed_requests
    target.cached_prompt_tokens += source.cached_prompt_tokens
    target.cache_write_prompt_tokens += source.cache_write_prompt_tokens
    target.cache_hit_requests += source.cache_hit_requests
    target.cache_write_requests += source.cache_write_requests
    target.saved_cost_usd += source.saved_cost_usd


def _merge_metrics_into(target: ThriftMetrics, source: ThriftMetrics) -> None:
    target.coalesced_requests += source.coalesced_requests
    target.recent_reuse_requests += source.recent_reuse_requests
    target.recent_reuse_prompt_tokens += source.recent_reuse_prompt_tokens
    target.recent_reuse_completion_tokens += source.recent_reuse_completion_tokens
    target.saved_prompt_tokens += source.saved_prompt_tokens
    target.saved_completion_tokens += source.saved_completion_tokens
    target.saved_cost_usd += source.saved_cost_usd
    target.compacted_tokens += source.compacted_tokens
    target.deferred_requests += source.deferred_requests
    target.cached_prompt_tokens += source.cached_prompt_tokens
    target.cache_write_prompt_tokens += source.cache_write_prompt_tokens
    target.cache_hit_requests += source.cache_hit_requests
    target.cache_write_requests += source.cache_write_requests

    for key, bucket in source.cache_efficiency_by_provider.items():
        _merge_cache_bucket_into(
            _get_cache_bucket(target.cache_efficiency_by_provider, key),
            bucket,
        )
    for key, bucket in source.cache_efficiency_by_model.items():
        _merge_cache_bucket_into(
            _get_cache_bucket(target.cache_efficiency_by_model, key),
            bucket,
        )


def _normalize_day_key(value: date | datetime) -> str:
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat()


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _record_coalesced_savings_on_metrics(
    metrics: ThriftMetrics,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: float | None = None,
) -> None:
    prompt_tokens = max(0, int(prompt_tokens))
    completion_tokens = max(0, int(completion_tokens))
    metrics.coalesced_requests += 1
    metrics.saved_prompt_tokens += prompt_tokens
    metrics.saved_completion_tokens += completion_tokens
    if estimated_cost_usd is None:
        estimated_cost_usd = (
            prompt_tokens + completion_tokens
        ) * PricingDefaults.ESTIMATED_TOKEN_PRICE
    metrics.saved_cost_usd += max(0.0, float(estimated_cost_usd))


def _record_recent_reuse_savings_on_metrics(
    metrics: ThriftMetrics,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: float | None = None,
) -> None:
    prompt_tokens = max(0, int(prompt_tokens))
    completion_tokens = max(0, int(completion_tokens))
    metrics.recent_reuse_requests += 1
    metrics.recent_reuse_prompt_tokens += prompt_tokens
    metrics.recent_reuse_completion_tokens += completion_tokens
    metrics.saved_prompt_tokens += prompt_tokens
    metrics.saved_completion_tokens += completion_tokens
    if estimated_cost_usd is None:
        estimated_cost_usd = (
            prompt_tokens + completion_tokens
        ) * PricingDefaults.ESTIMATED_TOKEN_PRICE
    metrics.saved_cost_usd += max(0.0, float(estimated_cost_usd))


def _record_compaction_savings_on_metrics(metrics: ThriftMetrics, tokens_saved: int) -> None:
    if tokens_saved <= 0:
        return
    metrics.compacted_tokens += int(tokens_saved)


def _record_deferred_requests_on_metrics(metrics: ThriftMetrics, request_count: int) -> None:
    if request_count <= 0:
        return
    metrics.deferred_requests += int(request_count)


def _record_model_request_on_metrics(metrics: ThriftMetrics, model: str) -> None:
    for bucket in _iter_cache_buckets_for_model(metrics, model):
        bucket.observed_requests += 1


def _record_prompt_cache_activity_on_metrics(
    metrics: ThriftMetrics,
    cached_prompt_tokens: int,
    cache_write_prompt_tokens: int,
    estimated_saved_cost_usd: float | None = None,
    model: str | None = None,
) -> None:
    cached_prompt_tokens = max(0, int(cached_prompt_tokens))
    cache_write_prompt_tokens = max(0, int(cache_write_prompt_tokens))
    if cached_prompt_tokens == 0 and cache_write_prompt_tokens == 0:
        return
    saved_cost_increment = 0.0
    if estimated_saved_cost_usd is not None:
        saved_cost_increment = max(0.0, float(estimated_saved_cost_usd))
    metrics.cached_prompt_tokens += cached_prompt_tokens
    metrics.cache_write_prompt_tokens += cache_write_prompt_tokens
    if cached_prompt_tokens > 0:
        metrics.cache_hit_requests += 1
    if cache_write_prompt_tokens > 0:
        metrics.cache_write_requests += 1
    metrics.saved_prompt_tokens += cached_prompt_tokens
    metrics.saved_cost_usd += saved_cost_increment

    for bucket in _iter_cache_buckets_for_model(metrics, model):
        bucket.cached_prompt_tokens += cached_prompt_tokens
        bucket.cache_write_prompt_tokens += cache_write_prompt_tokens
        if cached_prompt_tokens > 0:
            bucket.cache_hit_requests += 1
        if cache_write_prompt_tokens > 0:
            bucket.cache_write_requests += 1
        bucket.saved_cost_usd += saved_cost_increment


_request_metrics_var: ContextVar[ThriftMetrics | None] = ContextVar(
    "runtime_thrift_request_metrics",
    default=None,
)


@contextmanager
def thrift_request_scope() -> Iterator[ThriftMetrics]:
    current_metrics = _request_metrics_var.get()
    if current_metrics is not None:
        yield current_metrics
        return

    request_metrics = ThriftMetrics()
    token = _request_metrics_var.set(request_metrics)
    try:
        yield request_metrics
    finally:
        _request_metrics_var.reset(token)


def get_request_thrift_metrics_snapshot() -> Dict[str, Any]:
    request_metrics = _request_metrics_var.get()
    if request_metrics is None:
        return _snapshot_from_metrics(ThriftMetrics())
    return _snapshot_from_metrics(request_metrics)


class ThriftMetricsCollector:
    """In-memory collector for runtime thrift counters."""

    def __init__(
        self,
        persistence_path: Optional[str] = None,
        *,
        save_interval: int = 1,
        now_provider: Callable[[], date | datetime] | None = None,
    ) -> None:
        self._metrics = ThriftMetrics()
        self._daily_metrics: Dict[str, ThriftMetrics] = {}
        self._persistence_path = persistence_path
        self._save_interval = max(1, int(save_interval))
        self._record_count_since_save = 0
        self._now_provider = now_provider or datetime.now
        self._lock = Lock()
        self._load()

    def _current_day_key(self) -> str:
        return _normalize_day_key(self._now_provider())

    def _get_current_day_metrics(self) -> ThriftMetrics:
        day_key = self._current_day_key()
        day_metrics = self._daily_metrics.get(day_key)
        if day_metrics is None:
            day_metrics = ThriftMetrics()
            self._daily_metrics[day_key] = day_metrics
        return day_metrics

    def _serialize_days(self) -> Dict[str, Any]:
        return {
            "version": _PERSISTENCE_VERSION,
            "days": {
                day_key: _snapshot_from_metrics(metrics)
                for day_key, metrics in sorted(self._daily_metrics.items())
            },
        }

    def _rebuild_aggregate_metrics(self) -> None:
        aggregate = ThriftMetrics()
        for metrics in self._daily_metrics.values():
            _merge_metrics_into(aggregate, metrics)
        self._metrics = aggregate

    def _load(self) -> None:
        if not self._persistence_path or not os.path.exists(self._persistence_path):
            return
        try:
            with open(self._persistence_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                raise TypeError("runtime thrift metrics root must be a JSON object")
            raw_days = payload.get("days", {})
            if not isinstance(raw_days, dict):
                raise TypeError("runtime thrift metrics days must be a JSON object")

            loaded_days: Dict[str, ThriftMetrics] = {}
            for day_key, snapshot in raw_days.items():
                date.fromisoformat(str(day_key))
                if isinstance(snapshot, dict):
                    loaded_days[str(day_key)] = _metrics_from_snapshot(snapshot)

            self._daily_metrics = loaded_days
            self._rebuild_aggregate_metrics()
        except (
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning(
                "Runtime thrift metrics cache is corrupted. Starting empty: %s",
                exc,
            )
            self._metrics = ThriftMetrics()
            self._daily_metrics = {}

    def _save(self) -> None:
        if not self._persistence_path:
            return
        dir_path = os.path.dirname(self._persistence_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        payload = self._serialize_days()
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_path or ".", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
                os.replace(tmp_path, self._persistence_path)
            except BaseException:
                os.unlink(tmp_path)
                raise
        except OSError as exc:
            logger.warning("Runtime thrift metrics save failed: %s", exc)

    def _maybe_auto_save(self) -> None:
        if not self._persistence_path:
            return
        self._record_count_since_save += 1
        if self._record_count_since_save >= self._save_interval:
            self._save()
            self._record_count_since_save = 0

    def reset(self) -> None:
        with self._lock:
            self._metrics = ThriftMetrics()
            self._daily_metrics = {}
            self._record_count_since_save = 0
            self._save()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return _snapshot_from_metrics(self._metrics)

    def snapshot_for_dates(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if start_date is None and end_date is None:
                return _snapshot_from_metrics(self._metrics)

            start = _parse_date(start_date)
            end = _parse_date(end_date)
            if start is not None and end is not None and start > end:
                return _snapshot_from_metrics(ThriftMetrics())

            aggregate = ThriftMetrics()
            for day_key, metrics in self._daily_metrics.items():
                day_value = date.fromisoformat(day_key)
                if start is not None and day_value < start:
                    continue
                if end is not None and day_value > end:
                    continue
                _merge_metrics_into(aggregate, metrics)
            return _snapshot_from_metrics(aggregate)

    def record_coalesced_savings(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float | None = None,
    ) -> None:
        with self._lock:
            _record_coalesced_savings_on_metrics(
                self._metrics,
                prompt_tokens,
                completion_tokens,
                estimated_cost_usd,
            )
            _record_coalesced_savings_on_metrics(
                self._get_current_day_metrics(),
                prompt_tokens,
                completion_tokens,
                estimated_cost_usd,
            )
            self._maybe_auto_save()

    def record_recent_reuse_savings(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float | None = None,
    ) -> None:
        with self._lock:
            _record_recent_reuse_savings_on_metrics(
                self._metrics,
                prompt_tokens,
                completion_tokens,
                estimated_cost_usd,
            )
            _record_recent_reuse_savings_on_metrics(
                self._get_current_day_metrics(),
                prompt_tokens,
                completion_tokens,
                estimated_cost_usd,
            )
            self._maybe_auto_save()

    def record_compaction_savings(self, tokens_saved: int) -> None:
        with self._lock:
            _record_compaction_savings_on_metrics(self._metrics, tokens_saved)
            _record_compaction_savings_on_metrics(self._get_current_day_metrics(), tokens_saved)
            self._maybe_auto_save()

    def record_deferred_requests(self, request_count: int) -> None:
        with self._lock:
            _record_deferred_requests_on_metrics(self._metrics, request_count)
            _record_deferred_requests_on_metrics(self._get_current_day_metrics(), request_count)
            self._maybe_auto_save()

    def record_model_request(self, model: str) -> None:
        with self._lock:
            _record_model_request_on_metrics(self._metrics, model)
            _record_model_request_on_metrics(self._get_current_day_metrics(), model)
            self._maybe_auto_save()

    def record_prompt_cache_activity(
        self,
        cached_prompt_tokens: int,
        cache_write_prompt_tokens: int,
        estimated_saved_cost_usd: float | None = None,
        model: str | None = None,
    ) -> None:
        with self._lock:
            _record_prompt_cache_activity_on_metrics(
                self._metrics,
                cached_prompt_tokens,
                cache_write_prompt_tokens,
                estimated_saved_cost_usd,
                model,
            )
            _record_prompt_cache_activity_on_metrics(
                self._get_current_day_metrics(),
                cached_prompt_tokens,
                cache_write_prompt_tokens,
                estimated_saved_cost_usd,
                model,
            )
            self._maybe_auto_save()


_collector = ThriftMetricsCollector(
    persistence_path=CacheConfig.RUNTIME_THRIFT_METRICS_FILE,
    save_interval=CacheConfig.RUNTIME_THRIFT_SAVE_INTERVAL,
)


def get_thrift_metrics_snapshot() -> Dict[str, Any]:
    return _collector.snapshot()


def get_thrift_metrics_snapshot_for_dates(
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict[str, Any]:
    return _collector.snapshot_for_dates(start_date, end_date)


def reset_thrift_metrics() -> None:
    _collector.reset()


def record_coalesced_savings(
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: float | None = None,
) -> None:
    _collector.record_coalesced_savings(prompt_tokens, completion_tokens, estimated_cost_usd)
    request_metrics = _request_metrics_var.get()
    if request_metrics is not None:
        _record_coalesced_savings_on_metrics(
            request_metrics,
            prompt_tokens,
            completion_tokens,
            estimated_cost_usd,
        )


def record_recent_reuse_savings(
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: float | None = None,
) -> None:
    _collector.record_recent_reuse_savings(prompt_tokens, completion_tokens, estimated_cost_usd)
    request_metrics = _request_metrics_var.get()
    if request_metrics is not None:
        _record_recent_reuse_savings_on_metrics(
            request_metrics,
            prompt_tokens,
            completion_tokens,
            estimated_cost_usd,
        )


def record_compaction_savings(tokens_saved: int) -> None:
    _collector.record_compaction_savings(tokens_saved)
    request_metrics = _request_metrics_var.get()
    if request_metrics is not None:
        _record_compaction_savings_on_metrics(request_metrics, tokens_saved)


def record_deferred_requests(request_count: int) -> None:
    _collector.record_deferred_requests(request_count)
    request_metrics = _request_metrics_var.get()
    if request_metrics is not None:
        _record_deferred_requests_on_metrics(request_metrics, request_count)


def record_model_request(model: str) -> None:
    _collector.record_model_request(model)
    request_metrics = _request_metrics_var.get()
    if request_metrics is not None:
        _record_model_request_on_metrics(request_metrics, model)


def record_prompt_cache_activity(
    cached_prompt_tokens: int,
    cache_write_prompt_tokens: int,
    estimated_saved_cost_usd: float | None = None,
    model: str | None = None,
) -> None:
    _collector.record_prompt_cache_activity(
        cached_prompt_tokens,
        cache_write_prompt_tokens,
        estimated_saved_cost_usd,
        model,
    )
    request_metrics = _request_metrics_var.get()
    if request_metrics is not None:
        _record_prompt_cache_activity_on_metrics(
            request_metrics,
            cached_prompt_tokens,
            cache_write_prompt_tokens,
            estimated_saved_cost_usd,
            model,
        )


__all__ = [
    "ThriftMetrics",
    "ThriftMetricsCollector",
    "get_request_thrift_metrics_snapshot",
    "get_thrift_metrics_snapshot",
    "get_thrift_metrics_snapshot_for_dates",
    "record_coalesced_savings",
    "record_recent_reuse_savings",
    "record_compaction_savings",
    "record_deferred_requests",
    "record_model_request",
    "record_prompt_cache_activity",
    "reset_thrift_metrics",
    "thrift_request_scope",
]
