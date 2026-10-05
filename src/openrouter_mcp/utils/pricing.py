"""Pricing utilities for OpenRouter models."""

from __future__ import annotations

from math import isfinite
from typing import Any, Optional

from ..config.constants import PricingDefaults


def validate_usage_tokens(usage: dict[str, Any]) -> None:
    """Token accounting accepts nonnegative JSON integers only."""
    for name, value in usage.items():
        if name in {"prompt_tokens", "completion_tokens", "total_tokens"} and (
            type(value) is not int or value < 0
        ):
            raise ValueError(f"Invalid token usage counter: {name}")


def reported_usage_cost(usage: dict[str, Any]) -> float | None:
    """Read authoritative response spending, including a legitimate zero charge."""
    validate_usage_tokens(usage)
    value = usage.get("cost")
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value < 0
    ):
        raise ValueError("Invalid reported usage cost")
    return float(value)


def parse_price(value: Any) -> float:
    """Parse pricing values into a float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "")
        if not cleaned:
            return 0.0
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def _normalize_unit(price: float) -> float:
    """Normalize price to per-token units."""
    if price >= PricingDefaults.PER_1K_PRICE_THRESHOLD:
        return price / 1000.0
    return price


def _fill_missing_prices(
    prompt_price: float, completion_price: float, default_price: float
) -> tuple[float, float]:
    """Fill missing or zero prices using cross-fill or default fallback."""
    if prompt_price <= 0 and completion_price <= 0:
        return default_price, default_price
    if prompt_price <= 0:
        return completion_price, completion_price
    if completion_price <= 0:
        return prompt_price, prompt_price
    return prompt_price, completion_price


def normalize_pricing(
    pricing: Optional[dict[str, Any]],
    default_price: float = PricingDefaults.DEFAULT_TOKEN_PRICE,
    *,
    normalize_units: bool = True,
    fill_missing: bool = True,
) -> dict[str, float]:
    """Normalize pricing dict into prompt/completion floats.

    When normalize_units is True (default), values are converted to per-token
    units from per-1k token pricing when needed. When fill_missing is False,
    missing or zero values are left unchanged (no default or cross-fill).
    """
    pricing = pricing or {}
    prompt_price = parse_price(pricing.get("prompt"))
    completion_price = parse_price(pricing.get("completion"))

    if normalize_units:
        prompt_price = _normalize_unit(prompt_price)
        completion_price = _normalize_unit(completion_price)

    if fill_missing:
        prompt_price, completion_price = _fill_missing_prices(
            prompt_price, completion_price, default_price
        )

    return {"prompt": prompt_price, "completion": completion_price}


def cost_for_tokens(tokens: int, price: float) -> float:
    """Calculate cost for tokens using per-token or per-1K pricing."""
    if tokens <= 0 or price <= 0:
        return 0.0
    if price >= PricingDefaults.PER_1K_PRICE_THRESHOLD:
        return (tokens * price) / 1000.0
    return tokens * price


def _split_tokens(total_tokens: int) -> tuple[int, int]:
    """Split total tokens into prompt/completion halves."""
    if total_tokens <= 0:
        return 0, 0
    prompt_tokens = total_tokens // 2
    completion_tokens = total_tokens - prompt_tokens
    return prompt_tokens, completion_tokens


def estimate_cost_from_usage(
    usage: dict[str, int],
    pricing: dict[str, Any],
    default_price: float = PricingDefaults.DEFAULT_TOKEN_PRICE,
    *,
    pricing_is_normalized: bool = False,
) -> float:
    """Estimate spending, preserving explicit per-token prices when normalized."""
    prompt_price = parse_price(pricing.get("prompt"))
    completion_price = parse_price(pricing.get("completion"))
    if not pricing_is_normalized:
        prompt_price, completion_price = _fill_missing_prices(
            prompt_price, completion_price, default_price
        )

    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens) or 0

    if prompt_tokens == 0 and completion_tokens == 0 and total_tokens:
        prompt_tokens, completion_tokens = _split_tokens(total_tokens)

    if pricing_is_normalized:
        return prompt_tokens * prompt_price + completion_tokens * completion_price
    return cost_for_tokens(prompt_tokens, prompt_price) + cost_for_tokens(
        completion_tokens, completion_price
    )


def estimate_cost_from_tokens(
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    total_tokens: int,
    pricing: dict[str, Any],
    default_price: float = PricingDefaults.DEFAULT_TOKEN_PRICE,
) -> float:
    """Estimate total cost from explicit token counts."""
    usage = {
        "prompt_tokens": prompt_tokens or 0,
        "completion_tokens": completion_tokens or 0,
        "total_tokens": total_tokens or 0,
    }
    return estimate_cost_from_usage(usage, pricing, default_price)
