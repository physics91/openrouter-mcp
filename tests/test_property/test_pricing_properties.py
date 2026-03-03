"""Property-style tests for pricing invariants."""

from __future__ import annotations

import pytest

from openrouter_mcp.utils.pricing import estimate_cost_from_usage, normalize_pricing


@pytest.mark.property
def test_cost_is_monotonic_when_token_count_increases():
    """Total estimated cost should not decrease as token usage increases."""
    pricing = {"prompt": 0.00001, "completion": 0.00002}
    previous_cost = 0.0

    for total_tokens in range(0, 2501, 125):
        usage = {
            "prompt_tokens": total_tokens // 2,
            "completion_tokens": total_tokens - (total_tokens // 2),
            "total_tokens": total_tokens,
        }
        current_cost = estimate_cost_from_usage(usage, pricing)
        assert current_cost >= previous_cost
        previous_cost = current_cost


@pytest.mark.property
@pytest.mark.parametrize(
    "pricing,expected",
    [
        ({"prompt": "", "completion": ""}, {"prompt": 1e-6, "completion": 1e-6}),
        ({"prompt": "0.002", "completion": ""}, {"prompt": 0.002, "completion": 0.002}),
        ({"prompt": "", "completion": "0.001"}, {"prompt": 0.001, "completion": 0.001}),
    ],
)
def test_missing_price_fields_are_filled_consistently(pricing, expected):
    """Cross-fill and default fallback rules should be stable."""
    normalized = normalize_pricing(pricing, default_price=1e-6, normalize_units=False)
    assert normalized == expected
