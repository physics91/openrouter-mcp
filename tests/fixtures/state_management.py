"""
State management utilities for test isolation.

This module provides utilities for managing singleton state and ensuring
proper test isolation, particularly for lifecycle manager and shared
client instances.
"""

from contextlib import asynccontextmanager
from typing import Any, Optional


async def reset_singleton_state() -> None:
    """
    Reset all singleton state for test isolation.

    This function should be called before tests that require
    clean singleton state to prevent test interference.
    """
    # Reset lifecycle manager singleton
    try:
        import openrouter_mcp.collective_intelligence.lifecycle_manager as lm_module
        from openrouter_mcp.collective_intelligence.lifecycle_manager import (
            shutdown_lifecycle_manager,
        )

        # Shutdown existing manager if present
        if hasattr(lm_module, "_lifecycle_manager"):
            manager = getattr(lm_module, "_lifecycle_manager", None)
            if manager is not None:
                try:
                    await shutdown_lifecycle_manager()
                except Exception:
                    pass
            # Reset the singleton variable
            lm_module._lifecycle_manager = None
    except ImportError:
        pass

    # Reset shared client singleton
    try:
        from openrouter_mcp import mcp_registry

        if hasattr(mcp_registry, "_client_instance"):
            client = getattr(mcp_registry, "_client_instance", None)
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    pass
            mcp_registry._client_instance = None
    except (ImportError, AttributeError):
        pass


@asynccontextmanager
async def lifecycle_manager_scope(
    config: Optional[Any] = None,
    auto_shutdown: bool = True,
):
    """
    Async context manager for scoped lifecycle manager usage.

    Ensures proper setup and teardown of lifecycle manager state
    for test isolation.

    Args:
        config: Optional OperationalConfig for the manager
        auto_shutdown: Whether to automatically shutdown on exit

    Yields:
        The lifecycle manager instance

    Example:
        async with lifecycle_manager_scope() as manager:
            # Test code using manager
            result = await manager.get_consensus_engine()
    """
    from openrouter_mcp.collective_intelligence.lifecycle_manager import (
        get_lifecycle_manager,
        shutdown_lifecycle_manager,
    )

    # Reset any existing state
    await reset_singleton_state()

    manager = None
    try:
        # Get fresh manager instance
        manager = await get_lifecycle_manager(config)
        yield manager
    finally:
        if auto_shutdown and manager is not None:
            try:
                await shutdown_lifecycle_manager()
            except Exception:
                pass
            # Ensure singleton is cleared
            await reset_singleton_state()


class StateIsolationMixin:
    """
    Mixin class providing state isolation utilities for test classes.

    Add this mixin to test classes that need singleton state isolation.

    Example:
        class TestMyComponent(StateIsolationMixin):
            async def async_setup_method(self, method):
                await self.reset_state()

            async def test_something(self):
                async with self.lifecycle_scope() as manager:
                    # Test code
    """

    async def reset_state(self) -> None:
        """Reset all singleton state."""
        await reset_singleton_state()

    @asynccontextmanager
    async def lifecycle_scope(self, config: Optional[Any] = None):
        """Get a scoped lifecycle manager."""
        async with lifecycle_manager_scope(config) as manager:
            yield manager


__all__ = [
    "reset_singleton_state",
    "lifecycle_manager_scope",
    "StateIsolationMixin",
]
