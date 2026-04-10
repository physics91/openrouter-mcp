"""Helpers for attaching thrift metadata to handler responses."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..utils import estimate_cost_from_usage
from .summary import build_thrift_summary


async def estimate_response_cost_usd(
    client: Any,
    model: str,
    usage: Dict[str, Any] | None,
    *,
    logger: logging.Logger | None = None,
    log_context: str = "response",
) -> float:
    if not isinstance(usage, dict):
        return 0.0

    try:
        pricing = await client.get_model_pricing(model)
    except Exception:
        if logger is not None:
            logger.debug(
                "Failed to estimate %s cost for thrift summary",
                log_context,
                exc_info=True,
            )
        return 0.0

    if not isinstance(pricing, dict):
        return 0.0

    return round(float(estimate_cost_from_usage(usage, pricing)), 8)


def attach_thrift_metadata(
    payload: Dict[str, Any],
    thrift_metrics: Dict[str, Any],
    total_cost_usd: float,
    *,
    request_count: int = 1,
) -> Dict[str, Any]:
    enriched = dict(payload)
    enriched["thrift_metrics"] = thrift_metrics
    enriched["thrift_summary"] = build_thrift_summary(
        {
            "total_cost": total_cost_usd,
            "requests": max(0, int(request_count)),
        },
        thrift_metrics,
    )
    return enriched


def attach_thrift_metadata_from_payload(
    payload: Dict[str, Any],
    thrift_metrics: Dict[str, Any],
    *,
    total_cost_key: str = "total_cost",
) -> Dict[str, Any]:
    try:
        total_cost_usd = round(float(payload.get(total_cost_key, 0.0)), 8)
    except (TypeError, ValueError):
        total_cost_usd = 0.0

    try:
        request_count = int(payload.get("requests", 0) or 0)
    except (TypeError, ValueError):
        request_count = 0

    return attach_thrift_metadata(
        payload,
        thrift_metrics,
        total_cost_usd,
        request_count=request_count,
    )


async def enrich_response_with_thrift_metadata(
    client: Any,
    model: str,
    payload: Dict[str, Any],
    thrift_metrics: Dict[str, Any],
    *,
    logger: logging.Logger | None = None,
    log_context: str = "response",
    total_cost_override_usd: float | None = None,
) -> Dict[str, Any]:
    if total_cost_override_usd is None:
        total_cost_usd = await estimate_response_cost_usd(
            client,
            model,
            payload.get("usage"),
            logger=logger,
            log_context=log_context,
        )
    else:
        total_cost_usd = round(float(total_cost_override_usd), 8)
    return attach_thrift_metadata(
        payload,
        thrift_metrics,
        total_cost_usd,
        request_count=1,
    )


__all__ = [
    "attach_thrift_metadata",
    "attach_thrift_metadata_from_payload",
    "enrich_response_with_thrift_metadata",
    "estimate_response_cost_usd",
]
