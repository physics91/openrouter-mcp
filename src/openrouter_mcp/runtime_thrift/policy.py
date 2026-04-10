"""Runtime thrift feature flags and thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utils.env import get_env_value


@dataclass(frozen=True)
class RuntimeThriftPolicy:
    """Configuration knobs for runtime token thrift features."""

    enable_generation_coalescing: bool = True
    enable_context_compaction: bool = True
    enable_deferred_batch_lane: bool = True
    enable_prefix_cache_planner: bool = True
    max_interactive_prompt_tokens: Optional[int] = None
    compaction_trigger_ratio: float = 0.75
    coalescing_ttl_seconds: int = 30


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_float(
    value: Optional[str],
    default: float,
    *,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default

    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _parse_int(
    value: Optional[str],
    default: int,
    *,
    min_value: Optional[int] = None,
) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if min_value is not None:
        parsed = max(min_value, parsed)
    return parsed


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def get_runtime_thrift_policy() -> RuntimeThriftPolicy:
    """Load runtime thrift policy from environment variables."""
    return RuntimeThriftPolicy(
        enable_generation_coalescing=_parse_bool(
            get_env_value("OPENROUTER_THRIFT_ENABLE_GENERATION_COALESCING"), True
        ),
        enable_context_compaction=_parse_bool(
            get_env_value("OPENROUTER_THRIFT_ENABLE_CONTEXT_COMPACTION"), True
        ),
        enable_deferred_batch_lane=_parse_bool(
            get_env_value("OPENROUTER_THRIFT_ENABLE_DEFERRED_BATCH_LANE"), True
        ),
        enable_prefix_cache_planner=_parse_bool(
            get_env_value("OPENROUTER_THRIFT_ENABLE_PREFIX_CACHE_PLANNER"), True
        ),
        max_interactive_prompt_tokens=_parse_optional_int(
            get_env_value("OPENROUTER_THRIFT_MAX_INTERACTIVE_PROMPT_TOKENS")
        ),
        compaction_trigger_ratio=_parse_float(
            get_env_value("OPENROUTER_THRIFT_COMPACTION_TRIGGER_RATIO"),
            0.75,
            min_value=0.1,
            max_value=1.0,
        ),
        coalescing_ttl_seconds=_parse_int(
            get_env_value("OPENROUTER_THRIFT_COALESCING_TTL_SECONDS"),
            30,
            min_value=0,
        ),
    )


def reset_runtime_thrift_policy() -> None:
    """Compatibility hook for tests.

    Policy reads directly from the environment on each call, so no cached state
    needs clearing.
    """


__all__ = [
    "RuntimeThriftPolicy",
    "get_runtime_thrift_policy",
    "reset_runtime_thrift_policy",
]
