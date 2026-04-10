"""Prompt compaction helpers for long-running chat-style requests."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set

from ..collective_intelligence.semantic_similarity import ResponseGrouper
from ..utils.token_counter import count_message_tokens
from .metrics import record_compaction_savings
from .policy import get_runtime_thrift_policy

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_WINDOW_TOKENS = 8192
DEFAULT_COMPLETION_RESERVE_TOKENS = 1024
DEFAULT_TRIGGER_RATIO = 0.75
DEFAULT_RECENT_MESSAGE_COUNT = 4
SUMMARY_LINE_LIMIT = 8
SUMMARY_TEXT_LIMIT = 160
ASSISTANT_SIMILARITY_THRESHOLD = 0.92
SUMMARY_HEADER = "Conversation summary of earlier turns:"
NOISY_ROLES = {"tool", "function"}


@dataclass(frozen=True)
class CompactionResult:
    """Result of applying prompt compaction."""

    messages: List[Dict[str, Any]]
    was_compacted: bool
    original_prompt_tokens: int
    compacted_prompt_tokens: int
    context_window_tokens: int
    trigger_threshold_tokens: int

    @property
    def tokens_saved(self) -> int:
        return max(0, self.original_prompt_tokens - self.compacted_prompt_tokens)


def _leading_system_prefix_length(messages: Sequence[Dict[str, Any]]) -> int:
    prefix_length = 0
    for message in messages:
        if message.get("role") != "system":
            break
        prefix_length += 1
    return prefix_length


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return _normalize_text(content)

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return _normalize_text(" ".join(parts))

    return ""


def _truncate(text: str, limit: int = SUMMARY_TEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _select_assistant_representatives(messages: Sequence[Dict[str, Any]]) -> Set[int]:
    assistant_texts: List[str] = []
    assistant_indices: List[int] = []

    for idx, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        text = _extract_text(message.get("content"))
        if not text:
            continue
        assistant_texts.append(text)
        assistant_indices.append(idx)

    if len(assistant_texts) <= 1:
        return set(assistant_indices)

    groups = ResponseGrouper(similarity_threshold=ASSISTANT_SIMILARITY_THRESHOLD).group_responses(
        assistant_texts
    )
    representatives: Set[int] = set()
    for group in groups:
        chosen = max(group, key=lambda text_idx: len(assistant_texts[text_idx]))
        representatives.add(assistant_indices[chosen])
    return representatives


def _build_summary_message(messages: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    assistant_representatives = _select_assistant_representatives(messages)
    lines: List[str] = []
    noisy_count = 0

    for idx, message in enumerate(messages):
        role = str(message.get("role", "unknown"))
        if role in NOISY_ROLES:
            noisy_count += 1
            continue
        if role == "assistant" and idx not in assistant_representatives:
            continue

        text = _extract_text(message.get("content"))
        if not text:
            continue

        lines.append(f"- {role.capitalize()}: {_truncate(text)}")
        if len(lines) >= SUMMARY_LINE_LIMIT:
            break

    if noisy_count:
        lines.append(f"- Tool chatter omitted: {noisy_count} entries")

    if not lines:
        lines.append("- Earlier conversation omitted to stay within prompt budget.")

    return {
        "role": "assistant",
        "content": f"{SUMMARY_HEADER}\n" + "\n".join(lines),
    }


def _build_noop_result(
    messages: Sequence[Dict[str, Any]],
    prompt_tokens: int,
    context_window_tokens: int,
    trigger_threshold_tokens: int,
) -> CompactionResult:
    return CompactionResult(
        messages=list(messages),
        was_compacted=False,
        original_prompt_tokens=prompt_tokens,
        compacted_prompt_tokens=prompt_tokens,
        context_window_tokens=context_window_tokens,
        trigger_threshold_tokens=trigger_threshold_tokens,
    )


def compact_messages(
    messages: Sequence[Dict[str, Any]],
    model_id: str,
    context_window_tokens: int,
    max_completion_tokens: Optional[int] = None,
    trigger_ratio: Optional[float] = None,
    recent_message_count: int = DEFAULT_RECENT_MESSAGE_COUNT,
) -> CompactionResult:
    """Compact long conversational prompts while preserving recent overlap."""
    policy = get_runtime_thrift_policy()
    prompt_tokens = count_message_tokens(list(messages), model_id)
    if not policy.enable_context_compaction:
        return _build_noop_result(
            messages,
            prompt_tokens,
            context_window_tokens,
            prompt_tokens,
        )

    completion_reserve = (
        max_completion_tokens
        if max_completion_tokens is not None
        else min(DEFAULT_COMPLETION_RESERVE_TOKENS, max(1, context_window_tokens // 4))
    )
    available_prompt_budget = max(1, context_window_tokens - completion_reserve)
    max_interactive_prompt_tokens = policy.max_interactive_prompt_tokens
    if max_interactive_prompt_tokens is not None:
        available_prompt_budget = min(available_prompt_budget, max_interactive_prompt_tokens)

    effective_trigger_ratio = (
        policy.compaction_trigger_ratio if trigger_ratio is None else trigger_ratio
    )
    trigger_threshold_tokens = max(1, int(available_prompt_budget * effective_trigger_ratio))

    if prompt_tokens <= trigger_threshold_tokens:
        return _build_noop_result(
            messages,
            prompt_tokens,
            context_window_tokens,
            trigger_threshold_tokens,
        )

    prefix_length = _leading_system_prefix_length(messages)
    prefix = list(messages[:prefix_length])
    body = list(messages[prefix_length:])

    if len(body) <= recent_message_count:
        return _build_noop_result(
            messages,
            prompt_tokens,
            context_window_tokens,
            trigger_threshold_tokens,
        )

    archived_messages = body[:-recent_message_count]
    recent_messages = body[-recent_message_count:]
    if not archived_messages:
        return _build_noop_result(
            messages,
            prompt_tokens,
            context_window_tokens,
            trigger_threshold_tokens,
        )

    compacted_messages = prefix + [_build_summary_message(archived_messages)] + recent_messages
    compacted_prompt_tokens = count_message_tokens(compacted_messages, model_id)

    if compacted_prompt_tokens >= prompt_tokens:
        return _build_noop_result(
            messages,
            prompt_tokens,
            context_window_tokens,
            trigger_threshold_tokens,
        )

    record_compaction_savings(prompt_tokens - compacted_prompt_tokens)
    return CompactionResult(
        messages=compacted_messages,
        was_compacted=True,
        original_prompt_tokens=prompt_tokens,
        compacted_prompt_tokens=compacted_prompt_tokens,
        context_window_tokens=context_window_tokens,
        trigger_threshold_tokens=trigger_threshold_tokens,
    )


async def _resolve_context_window_tokens(client: Any, model_id: str) -> int:
    try:
        cache = client.model_cache
    except Exception:
        cache = getattr(client, "_model_cache", None)

    if cache is not None and hasattr(cache, "get_model_info"):
        try:
            model_info = await cache.get_model_info(model_id)
            context_length = (
                model_info.get("context_length") if isinstance(model_info, dict) else None
            )
            if isinstance(context_length, (int, float)) and context_length > 0:
                return int(context_length)
        except Exception as exc:
            logger.debug("Failed to resolve context length for %s: %s", model_id, exc)

    return DEFAULT_CONTEXT_WINDOW_TOKENS


async def compact_messages_for_model(
    client: Any,
    model_id: str,
    messages: Sequence[Dict[str, Any]],
    max_completion_tokens: Optional[int] = None,
    trigger_ratio: Optional[float] = None,
    recent_message_count: int = DEFAULT_RECENT_MESSAGE_COUNT,
) -> CompactionResult:
    """Resolve model context size and compact messages if the prompt is too large."""
    context_window_tokens = await _resolve_context_window_tokens(client, model_id)
    return compact_messages(
        messages=messages,
        model_id=model_id,
        context_window_tokens=context_window_tokens,
        max_completion_tokens=max_completion_tokens,
        trigger_ratio=trigger_ratio,
        recent_message_count=recent_message_count,
    )


__all__ = ["CompactionResult", "compact_messages", "compact_messages_for_model"]
