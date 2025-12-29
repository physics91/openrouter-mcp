"""Async utilities for DRY usage across modules."""

from __future__ import annotations

import inspect
from typing import Any


async def maybe_await(value: Any) -> Any:
    """Await value if it is awaitable, otherwise return it as-is."""
    if inspect.isawaitable(value):
        return await value
    return value


__all__ = ["maybe_await"]
