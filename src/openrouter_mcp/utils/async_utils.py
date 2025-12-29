"""Async utilities for DRY usage across modules."""

from __future__ import annotations

import inspect
from typing import Any, AsyncIterable, List, TypeVar

T = TypeVar("T")


async def maybe_await(value: Any) -> Any:
    """Await value if it is awaitable, otherwise return it as-is."""
    if inspect.isawaitable(value):
        return await value
    return value


async def collect_async_iterable(iterable: AsyncIterable[T]) -> List[T]:
    """Collect items from an async iterable into a list."""
    items: List[T] = []
    async for item in iterable:
        items.append(item)
    return items


__all__ = ["maybe_await", "collect_async_iterable"]
