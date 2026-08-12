"""Boundary regressions for model metadata quality scoring."""

from typing import Any

import pytest

from openrouter_mcp.utils.metadata import calculate_quality_score


def _quality_model(
    *,
    context_length: int = 0,
    max_output: int = 0,
    prompt_price_per_1k: float = 0.001,
) -> dict[str, Any]:
    prompt_price_per_token = prompt_price_per_1k / 1000.0
    return {
        "id": "unknown/model",
        "context_length": context_length,
        "top_provider": {"max_completion_tokens": max_output},
        "pricing": {
            "prompt": prompt_price_per_token,
            "completion": prompt_price_per_token,
        },
        "architecture": {"modality": "text"},
    }


@pytest.mark.parametrize(
    ("context_length", "expected_score"),
    [
        (7_999, 5.0),
        (8_000, 5.5),
        (31_999, 5.5),
        (32_000, 6.0),
        (99_999, 6.0),
        (100_000, 6.5),
        (199_999, 6.5),
        (200_000, 7.0),
    ],
)
def test_context_quality_boundaries(context_length: int, expected_score: float) -> None:
    assert calculate_quality_score(
        _quality_model(context_length=context_length)
    ) == pytest.approx(expected_score)


@pytest.mark.parametrize(
    ("max_output", "expected_score"),
    [
        (4_095, 5.0),
        (4_096, 5.5),
        (8_191, 5.5),
        (8_192, 6.0),
    ],
)
def test_output_quality_boundaries(max_output: int, expected_score: float) -> None:
    assert calculate_quality_score(
        _quality_model(max_output=max_output)
    ) == pytest.approx(expected_score)


@pytest.mark.parametrize(
    ("prompt_price_per_1k", "expected_score"),
    [
        (0.0, 4.0),
        (0.001, 5.0),
        (0.0011, 5.5),
        (0.01, 5.5),
        (0.0101, 6.5),
    ],
)
def test_pricing_quality_boundaries(
    prompt_price_per_1k: float, expected_score: float
) -> None:
    assert calculate_quality_score(
        _quality_model(prompt_price_per_1k=prompt_price_per_1k)
    ) == pytest.approx(expected_score)
