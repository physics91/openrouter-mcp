"""Provider-aware prompt prefix cache planning."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from ..utils.token_counter import count_message_tokens
from .policy import get_runtime_thrift_policy

DEFAULT_CACHE_CONTROL = {"type": "ephemeral"}


@dataclass(frozen=True)
class PrefixCachePlan:
    """Planned explicit cache breakpoint placement for a request."""

    messages: List[Dict[str, Any]]
    applied: bool
    provider: Optional[str]
    breakpoint_message_index: Optional[int]
    cacheable_prompt_tokens: int
    minimum_cacheable_tokens: Optional[int]


def _infer_explicit_cache_provider(model_id: str) -> Optional[str]:
    normalized = model_id.lower()
    if normalized.startswith("anthropic/"):
        return "anthropic"
    if normalized.startswith("google/") and "gemini" in normalized:
        return "gemini"
    return None


def _minimum_cacheable_tokens(model_id: str, provider: str) -> int:
    normalized = model_id.lower()

    if provider == "anthropic":
        if "claude-opus-4.6" in normalized or "claude-opus-4.5" in normalized:
            return 4096
        if "claude-haiku-4.5" in normalized:
            return 4096
        if "claude-sonnet-4.6" in normalized or "claude-haiku-3.5" in normalized:
            return 2048
        return 1024

    if provider == "gemini":
        if "2.5-flash" in normalized:
            return 1028
        if "2.5-pro" in normalized:
            return 2048
        return 4096

    return 0


def _has_existing_cache_control(messages: Sequence[Dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and "cache_control" in item:
                return True
    return False


def _apply_breakpoint_to_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    content = message.get("content")
    updated = deepcopy(message)

    if isinstance(content, str):
        text = content.strip()
        if not text:
            return None
        updated["content"] = [
            {
                "type": "text",
                "text": content,
                "cache_control": dict(DEFAULT_CACHE_CONTROL),
            }
        ]
        return updated

    if isinstance(content, list):
        updated_content = deepcopy(content)
        for idx in range(len(updated_content) - 1, -1, -1):
            item = updated_content[idx]
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            if "cache_control" in item:
                return updated
            item["cache_control"] = dict(DEFAULT_CACHE_CONTROL)
            updated["content"] = updated_content
            return updated

    return None


def apply_prefix_cache_planner(
    messages: Sequence[Dict[str, Any]],
    model_id: str,
) -> PrefixCachePlan:
    """Insert an explicit per-block cache breakpoint for providers that require it."""
    policy = get_runtime_thrift_policy()
    message_list = [deepcopy(message) for message in messages]

    if not policy.enable_prefix_cache_planner or len(message_list) < 2:
        return PrefixCachePlan(
            messages=message_list,
            applied=False,
            provider=None,
            breakpoint_message_index=None,
            cacheable_prompt_tokens=0,
            minimum_cacheable_tokens=None,
        )

    provider = _infer_explicit_cache_provider(model_id)
    if provider is None or _has_existing_cache_control(message_list):
        return PrefixCachePlan(
            messages=message_list,
            applied=False,
            provider=provider,
            breakpoint_message_index=None,
            cacheable_prompt_tokens=0,
            minimum_cacheable_tokens=None
            if provider is None
            else _minimum_cacheable_tokens(model_id, provider),
        )

    minimum_tokens = _minimum_cacheable_tokens(model_id, provider)
    chosen_index: Optional[int] = None
    chosen_tokens = 0

    for idx in range(len(message_list) - 1):
        candidate_tokens = count_message_tokens(message_list[: idx + 1], model_id)
        if candidate_tokens < minimum_tokens:
            continue
        if _apply_breakpoint_to_message(message_list[idx]) is None:
            continue
        chosen_index = idx
        chosen_tokens = candidate_tokens

    if chosen_index is None:
        return PrefixCachePlan(
            messages=message_list,
            applied=False,
            provider=provider,
            breakpoint_message_index=None,
            cacheable_prompt_tokens=0,
            minimum_cacheable_tokens=minimum_tokens,
        )

    updated_messages = list(message_list)
    updated_messages[chosen_index] = (
        _apply_breakpoint_to_message(message_list[chosen_index]) or message_list[chosen_index]
    )

    return PrefixCachePlan(
        messages=updated_messages,
        applied=True,
        provider=provider,
        breakpoint_message_index=chosen_index,
        cacheable_prompt_tokens=chosen_tokens,
        minimum_cacheable_tokens=minimum_tokens,
    )


__all__ = ["PrefixCachePlan", "apply_prefix_cache_planner"]
