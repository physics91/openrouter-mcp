"""Human-readable summaries for thrift metrics."""

from __future__ import annotations

from typing import Any, Dict


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


def _build_cache_bucket_summary(bucket: Dict[str, Any]) -> Dict[str, Any]:
    observed_requests = _as_int(bucket.get("observed_requests"))
    cached_prompt_tokens = _as_int(bucket.get("cached_prompt_tokens"))
    cache_write_prompt_tokens = _as_int(bucket.get("cache_write_prompt_tokens"))
    cache_hit_requests = _as_int(bucket.get("cache_hit_requests"))
    cache_write_requests = _as_int(bucket.get("cache_write_requests"))
    saved_cost_usd = round(_as_float(bucket.get("saved_cost_usd")), 8)

    cache_hit_request_rate_pct = 0.0
    cache_write_request_rate_pct = 0.0
    if observed_requests > 0:
        cache_hit_request_rate_pct = round((cache_hit_requests / observed_requests) * 100.0, 2)
        cache_write_request_rate_pct = round(
            (cache_write_requests / observed_requests) * 100.0,
            2,
        )

    reuse_to_write_ratio = None
    if cache_write_prompt_tokens > 0:
        reuse_to_write_ratio = round(cached_prompt_tokens / cache_write_prompt_tokens, 4)

    return {
        "observed_requests": observed_requests,
        "cached_prompt_tokens": cached_prompt_tokens,
        "cache_write_prompt_tokens": cache_write_prompt_tokens,
        "cache_hit_requests": cache_hit_requests,
        "cache_write_requests": cache_write_requests,
        "cache_hit_request_rate_pct": cache_hit_request_rate_pct,
        "cache_write_request_rate_pct": cache_write_request_rate_pct,
        "reuse_to_write_ratio": reuse_to_write_ratio,
        "saved_cost_usd": saved_cost_usd,
    }


def _build_cache_efficiency_breakdown(metrics: Dict[str, Any], key: str) -> Dict[str, Any]:
    raw_breakdown = metrics.get(key)
    if not isinstance(raw_breakdown, dict):
        return {}

    summarized = {
        str(bucket_key): _build_cache_bucket_summary(bucket_value)
        for bucket_key, bucket_value in raw_breakdown.items()
        if isinstance(bucket_value, dict)
    }
    return dict(
        sorted(
            summarized.items(),
            key=lambda item: (
                -_as_float(item[1].get("saved_cost_usd")),
                -_as_int(item[1].get("cached_prompt_tokens")),
                item[0],
            ),
        )
    )


def _build_cache_hotspots(
    providers: Dict[str, Any],
    models: Dict[str, Any],
) -> Dict[str, Any]:
    def build_reason(bucket: Dict[str, Any]) -> str:
        cache_hit_request_rate_pct = round(
            _as_float(bucket.get("cache_hit_request_rate_pct")),
            2,
        )
        cache_write_request_rate_pct = round(
            _as_float(bucket.get("cache_write_request_rate_pct")),
            2,
        )
        reuse_to_write_ratio = bucket.get("reuse_to_write_ratio")
        if reuse_to_write_ratio is None:
            return (
                "Cache savings exist, but reuse depth is still too shallow to explain the hotspot"
            )

        reuse_to_write_ratio = round(_as_float(reuse_to_write_ratio), 4)

        if cache_hit_request_rate_pct >= 50.0 and reuse_to_write_ratio >= 4.0:
            return (
                "High hit rate and strong reuse-to-write ratio make this a primary savings source"
            )

        if (
            reuse_to_write_ratio >= 4.0
            and cache_hit_request_rate_pct >= cache_write_request_rate_pct
        ):
            return "Moderate hit rate, but each cache write gets reused multiple times"

        if (
            cache_hit_request_rate_pct >= cache_write_request_rate_pct
            and reuse_to_write_ratio >= 2.0
        ):
            return "Hit volume keeps pace with writes, so warming converts into real savings"

        if cache_write_request_rate_pct > cache_hit_request_rate_pct:
            return "Cache writes are visible, but hits are not keeping up yet"

        return "Some savings exist, but cache efficiency is still middling"

    def summarize(
        breakdown: Dict[str, Any],
        *,
        key_name: str,
    ) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        for bucket_key, bucket in breakdown.items():
            if not isinstance(bucket, dict):
                continue
            items.append(
                {
                    key_name: str(bucket_key),
                    "saved_cost_usd": round(_as_float(bucket.get("saved_cost_usd")), 8),
                    "cached_prompt_tokens": _as_int(bucket.get("cached_prompt_tokens")),
                    "cache_hit_request_rate_pct": round(
                        _as_float(bucket.get("cache_hit_request_rate_pct")),
                        2,
                    ),
                    "cache_write_request_rate_pct": round(
                        _as_float(bucket.get("cache_write_request_rate_pct")),
                        2,
                    ),
                    "reuse_to_write_ratio": (
                        None
                        if bucket.get("reuse_to_write_ratio") is None
                        else round(_as_float(bucket.get("reuse_to_write_ratio")), 4)
                    ),
                    "reason": build_reason(bucket),
                }
            )

        items.sort(
            key=lambda item: (
                -_as_float(item.get("saved_cost_usd")),
                -_as_int(item.get("cached_prompt_tokens")),
                str(item.get(key_name)),
            )
        )
        return items[:3]

    return {
        "providers": summarize(providers, key_name="provider"),
        "models": summarize(models, key_name="model"),
    }


def _build_cache_deadspots(
    providers: Dict[str, Any],
    models: Dict[str, Any],
) -> Dict[str, Any]:
    def build_reason(bucket: Dict[str, Any]) -> str:
        cache_hit_requests = _as_int(bucket.get("cache_hit_requests"))
        cache_hit_request_rate_pct = round(
            _as_float(bucket.get("cache_hit_request_rate_pct")),
            2,
        )
        cache_write_request_rate_pct = round(
            _as_float(bucket.get("cache_write_request_rate_pct")),
            2,
        )
        reuse_to_write_ratio = round(
            _as_float(bucket.get("reuse_to_write_ratio")),
            4,
        )

        if cache_hit_requests == 0:
            return "Cache writes are piling up, but zero hits means warmups are being wasted"

        if cache_hit_request_rate_pct < (cache_write_request_rate_pct / 2.0):
            return "Cache writes are visible, but hit conversion is still weak"

        if reuse_to_write_ratio < 1.0:
            return (
                "Some hits exist, but reuse depth is still too shallow to justify the warmup cost"
            )

        return "Cache warming is already paying off here, so this bucket is not a real deadspot"

    def summarize(
        breakdown: Dict[str, Any],
        *,
        key_name: str,
    ) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        for bucket_key, bucket in breakdown.items():
            if not isinstance(bucket, dict):
                continue

            cache_write_prompt_tokens = _as_int(bucket.get("cache_write_prompt_tokens"))
            if cache_write_prompt_tokens <= 0:
                continue

            cache_hit_request_rate_pct = round(
                _as_float(bucket.get("cache_hit_request_rate_pct")),
                2,
            )
            cache_write_request_rate_pct = round(
                _as_float(bucket.get("cache_write_request_rate_pct")),
                2,
            )
            reuse_to_write_ratio = round(
                _as_float(bucket.get("reuse_to_write_ratio")),
                4,
            )

            if (
                cache_hit_request_rate_pct >= cache_write_request_rate_pct
                and reuse_to_write_ratio >= 1.0
            ):
                continue

            items.append(
                {
                    key_name: str(bucket_key),
                    "saved_cost_usd": round(_as_float(bucket.get("saved_cost_usd")), 8),
                    "cached_prompt_tokens": _as_int(bucket.get("cached_prompt_tokens")),
                    "cache_hit_request_rate_pct": cache_hit_request_rate_pct,
                    "cache_write_request_rate_pct": cache_write_request_rate_pct,
                    "reuse_to_write_ratio": reuse_to_write_ratio,
                    "reason": build_reason(bucket),
                }
            )

        items.sort(
            key=lambda item: (
                -int(_as_float(item.get("cache_hit_request_rate_pct")) <= 0.0),
                -round(
                    _as_float(item.get("cache_write_request_rate_pct"))
                    - _as_float(item.get("cache_hit_request_rate_pct")),
                    2,
                ),
                _as_float(item.get("reuse_to_write_ratio")),
                -_as_float(item.get("cache_write_request_rate_pct")),
                -_as_int(item.get("cached_prompt_tokens")),
                str(item.get(key_name)),
            )
        )
        return items[:3]

    return {
        "providers": summarize(providers, key_name="provider"),
        "models": summarize(models, key_name="model"),
    }


def build_thrift_summary(stats: Dict[str, Any], thrift_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact, human-readable thrift summary."""
    saved_cost_usd = round(_as_float(thrift_metrics.get("saved_cost_usd")), 8)
    total_cost_usd = _as_float(stats.get("total_cost"))
    request_count = _as_int(stats.get("requests"))
    estimated_cost_without_thrift_usd = round(total_cost_usd + saved_cost_usd, 8)

    cached_prompt_tokens = _as_int(thrift_metrics.get("cached_prompt_tokens"))
    cache_write_prompt_tokens = _as_int(thrift_metrics.get("cache_write_prompt_tokens"))
    cache_hit_requests = _as_int(thrift_metrics.get("cache_hit_requests"))
    cache_write_requests = _as_int(thrift_metrics.get("cache_write_requests"))
    compacted_tokens = _as_int(thrift_metrics.get("compacted_tokens"))
    recent_reuse_prompt_tokens = _as_int(thrift_metrics.get("recent_reuse_prompt_tokens"))
    coalesced_requests = _as_int(thrift_metrics.get("coalesced_requests"))
    recent_reuse_requests = _as_int(thrift_metrics.get("recent_reuse_requests"))
    deferred_requests = _as_int(thrift_metrics.get("deferred_requests"))
    saved_prompt_tokens = _as_int(thrift_metrics.get("saved_prompt_tokens"))
    coalesced_prompt_tokens = max(
        0,
        saved_prompt_tokens - cached_prompt_tokens - recent_reuse_prompt_tokens,
    )

    effective_cost_reduction_pct = 0.0
    if estimated_cost_without_thrift_usd > 0:
        effective_cost_reduction_pct = round(
            (saved_cost_usd / estimated_cost_without_thrift_usd) * 100.0,
            2,
        )

    cache_hit_share_pct = 0.0
    if saved_prompt_tokens > 0:
        cache_hit_share_pct = round(
            (cached_prompt_tokens / saved_prompt_tokens) * 100.0,
            2,
        )

    reuse_to_write_ratio = None
    if cache_write_prompt_tokens > 0:
        reuse_to_write_ratio = round(cached_prompt_tokens / cache_write_prompt_tokens, 4)

    cache_hit_request_rate_pct = 0.0
    cache_write_request_rate_pct = 0.0
    if request_count > 0:
        cache_hit_request_rate_pct = round((cache_hit_requests / request_count) * 100.0, 2)
        cache_write_request_rate_pct = round(
            (cache_write_requests / request_count) * 100.0,
            2,
        )

    provider_breakdown = _build_cache_efficiency_breakdown(
        thrift_metrics,
        "cache_efficiency_by_provider",
    )
    model_breakdown = _build_cache_efficiency_breakdown(
        thrift_metrics,
        "cache_efficiency_by_model",
    )

    return {
        "saved_cost_usd": saved_cost_usd,
        "estimated_cost_without_thrift_usd": estimated_cost_without_thrift_usd,
        "effective_cost_reduction_pct": effective_cost_reduction_pct,
        "prompt_savings_breakdown": {
            "cache_reuse_tokens": cached_prompt_tokens,
            "coalesced_prompt_tokens": coalesced_prompt_tokens,
            "recent_reuse_prompt_tokens": recent_reuse_prompt_tokens,
            "compacted_tokens": compacted_tokens,
        },
        "request_savings_breakdown": {
            "coalesced_requests": coalesced_requests,
            "recent_reuse_requests": recent_reuse_requests,
            "deferred_requests": deferred_requests,
        },
        "cache_efficiency": {
            "cached_prompt_tokens": cached_prompt_tokens,
            "cache_write_prompt_tokens": cache_write_prompt_tokens,
            "cache_hit_requests": cache_hit_requests,
            "cache_write_requests": cache_write_requests,
            "cache_hit_request_rate_pct": cache_hit_request_rate_pct,
            "cache_write_request_rate_pct": cache_write_request_rate_pct,
            "cache_hit_share_of_saved_prompt_tokens_pct": cache_hit_share_pct,
            "reuse_to_write_ratio": reuse_to_write_ratio,
        },
        "cache_efficiency_by_provider": provider_breakdown,
        "cache_efficiency_by_model": model_breakdown,
        "cache_hotspots": _build_cache_hotspots(
            provider_breakdown,
            model_breakdown,
        ),
        "cache_deadspots": _build_cache_deadspots(
            provider_breakdown,
            model_breakdown,
        ),
    }


__all__ = ["build_thrift_summary"]
