"""Message utilities for consistent request serialization."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def serialize_messages(messages: Iterable[Any]) -> List[Dict[str, Any]]:
    """Convert message objects to dictionaries expected by the client."""
    serialized: List[Dict[str, Any]] = []

    for message in messages:
        if isinstance(message, dict):
            serialized.append(message)
            continue

        if hasattr(message, "model_dump"):
            serialized.append(message.model_dump())
            continue

        if hasattr(message, "dict"):
            serialized.append(message.dict())
            continue

        if hasattr(message, "role") and hasattr(message, "content"):
            serialized.append(
                {
                    "role": message.role,
                    "content": message.content,
                }
            )
            continue

        raise TypeError(f"Unsupported message type: {type(message)!r}")

    return serialized


__all__ = ["serialize_messages"]
