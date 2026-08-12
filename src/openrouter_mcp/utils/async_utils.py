"""Async utilities for DRY usage across modules."""

from __future__ import annotations

import asyncio
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


def raise_first_fatal_result(results: list[Any]) -> None:
    """Propagate the first fatal fanout result while preserving isolated failures."""
    for result in results:
        if isinstance(result, BaseException) and not isinstance(
            result, (Exception, asyncio.CancelledError)
        ):
            raise result


async def await_cleanup_future(future: "asyncio.Future[T]") -> T:
    """Finish and reap cleanup work before preserving its first interruption."""
    first_failure: BaseException | None = None

    while not future.done():
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError as exc:
            if first_failure is None:
                first_failure = exc
        except BaseException as exc:
            if first_failure is None:
                first_failure = exc
            break

    try:
        result = future.result()
    except BaseException as exc:
        if first_failure is None:
            first_failure = exc

    if first_failure is not None:
        raise first_failure
    return result


__all__ = [
    "await_cleanup_future",
    "collect_async_iterable",
    "maybe_await",
    "raise_first_fatal_result",
]
