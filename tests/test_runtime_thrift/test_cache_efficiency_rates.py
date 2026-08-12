from unittest.mock import Mock, call

import pytest

from src.openrouter_mcp.collective_intelligence import adaptive_router as router_module
from src.openrouter_mcp.collective_intelligence.adaptive_router import AdaptiveRouter
from src.openrouter_mcp.runtime_thrift import summary as summary_module
from src.openrouter_mcp.runtime_thrift.summary import (
    _build_cache_bucket_summary,
    _calculate_cache_efficiency_rates,
)

_SUMMARY_KEYS = [
    "observed_requests",
    "cached_prompt_tokens",
    "cache_write_prompt_tokens",
    "cache_hit_requests",
    "cache_write_requests",
    "cache_hit_request_rate_pct",
    "cache_write_request_rate_pct",
    "reuse_to_write_ratio",
    "saved_cost_usd",
]


@pytest.mark.unit
@pytest.mark.parametrize(
    (
        "observed_requests",
        "cached_prompt_tokens",
        "cache_write_prompt_tokens",
        "cache_hit_requests",
        "cache_write_requests",
        "expected",
    ),
    [
        (
            0,
            10,
            5,
            1,
            1,
            {
                "cache_hit_request_rate_pct": 0.0,
                "cache_write_request_rate_pct": 0.0,
                "reuse_to_write_ratio": 2.0,
            },
        ),
        (
            -1,
            10,
            -2,
            1,
            1,
            {
                "cache_hit_request_rate_pct": 0.0,
                "cache_write_request_rate_pct": 0.0,
                "reuse_to_write_ratio": None,
            },
        ),
        (
            3,
            10,
            4,
            2,
            1,
            {
                "cache_hit_request_rate_pct": 66.67,
                "cache_write_request_rate_pct": 33.33,
                "reuse_to_write_ratio": 2.5,
            },
        ),
    ],
)
def test_calculate_cache_efficiency_rates_preserves_denominators_and_rounding(
    observed_requests,
    cached_prompt_tokens,
    cache_write_prompt_tokens,
    cache_hit_requests,
    cache_write_requests,
    expected,
):
    assert (
        _calculate_cache_efficiency_rates(
            observed_requests,
            cached_prompt_tokens,
            cache_write_prompt_tokens,
            cache_hit_requests,
            cache_write_requests,
        )
        == expected
    )


@pytest.mark.unit
def test_runtime_summary_delegates_forgiving_normalized_counters(monkeypatch):
    rates = {
        "cache_hit_request_rate_pct": 10.0,
        "cache_write_request_rate_pct": 20.0,
        "reuse_to_write_ratio": 3.0,
    }
    calculate = Mock(return_value=rates)
    monkeypatch.setattr(summary_module, "_calculate_cache_efficiency_rates", calculate)

    result = _build_cache_bucket_summary(
        {
            "observed_requests": -2,
            "cached_prompt_tokens": -3,
            "cache_write_prompt_tokens": -4,
            "cache_hit_requests": -5,
            "cache_write_requests": -6,
            "saved_cost_usd": "1.25",
        }
    )

    assert calculate.call_args_list == [call(-2, -3, -4, -5, -6)]
    assert list(result) == _SUMMARY_KEYS
    assert result == {
        "observed_requests": -2,
        "cached_prompt_tokens": -3,
        "cache_write_prompt_tokens": -4,
        "cache_hit_requests": -5,
        "cache_write_requests": -6,
        **rates,
        "saved_cost_usd": 1.25,
    }


@pytest.mark.unit
def test_adaptive_summary_delegates_strict_clamped_counters(monkeypatch):
    rates = {
        "cache_hit_request_rate_pct": 10.0,
        "cache_write_request_rate_pct": 20.0,
        "reuse_to_write_ratio": 3.0,
    }
    calculate = Mock(return_value=rates)
    monkeypatch.setattr(router_module, "_calculate_cache_efficiency_rates", calculate)
    router = object.__new__(AdaptiveRouter)

    result = router._summarize_thrift_bucket(
        {
            "observed_requests": -2,
            "cached_prompt_tokens": -3,
            "cache_write_prompt_tokens": -4,
            "cache_hit_requests": -5,
            "cache_write_requests": -6,
            "saved_cost_usd": "1.25",
        }
    )

    assert calculate.call_args_list == [call(0, 0, 0, 0, 0)]
    assert list(result) == _SUMMARY_KEYS
    assert result == {
        "observed_requests": 0,
        "cached_prompt_tokens": 0,
        "cache_write_prompt_tokens": 0,
        "cache_hit_requests": 0,
        "cache_write_requests": 0,
        **rates,
        "saved_cost_usd": 1.25,
    }
