#!/usr/bin/env python3

"""
MCP Registry - Shared FastMCP Instance and OpenRouter Client Manager

This module provides:
1. Single, shared FastMCP instance to prevent duplicate tool registration
2. Singleton OpenRouterClient manager to prevent redundant client creation
3. Thread-safe access to shared resources

Architecture Pattern:
    - Single source of truth for the MCP instance and OpenRouter client
    - Prevents circular imports by keeping instances isolated
    - Enables proper tool registration across multiple handler modules
    - All handlers must import 'mcp' and 'get_openrouter_client' from this module

Usage:
    from openrouter_mcp.mcp_registry import mcp, get_openrouter_client

    @mcp.tool()
    async def my_tool(...):
        client = await get_openrouter_client()
        # Use client without async context manager (already managed)
        result = await client.list_models()
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Tuple

from fastmcp import FastMCP

from .config.constants import APIConfig, CacheConfig, EnvVars
from .utils.env import get_env_value, get_required_env

if TYPE_CHECKING:
    from .client.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# Create the single shared FastMCP instance
# This instance will be used by all handlers for tool registration
mcp = FastMCP("openrouter-mcp")

# Singleton client instance and lock for thread-safe initialization
_client_instance: Optional["OpenRouterClient"] = None
_client_lock: Optional[asyncio.Lock] = None
_client_initialized = False
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_client_lock() -> asyncio.Lock:
    global _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    return _client_lock


def _shared_client_is_closed(client: Optional["OpenRouterClient"]) -> bool:
    """Return True when the wrapped HTTP client has already been closed."""
    if client is None:
        return True
    http_client = getattr(client, "_client", None)
    return bool(getattr(http_client, "is_closed", False))


def _inspect_shared_client_reuse(
    client: "OpenRouterClient",
    owner_loop: Optional[asyncio.AbstractEventLoop],
    current_loop: asyncio.AbstractEventLoop,
    env_key: Optional[str],
) -> Tuple[bool, bool, bool]:
    loop_matches = owner_loop is None or owner_loop is current_loop
    loop_closed = owner_loop.is_closed() if owner_loop is not None else False
    key_matches = (not env_key) or getattr(client, "api_key", None) == env_key
    client_closed = _shared_client_is_closed(client)
    reusable = loop_matches and not loop_closed and not client_closed and key_matches
    return reusable, loop_closed, client_closed


async def _cleanup_stale_shared_client(
    client: "OpenRouterClient",
    *,
    loop_closed: bool,
    client_closed: bool,
) -> None:
    """Clean up a stale shared client when its owning resources are usable."""
    try:
        if not loop_closed and not client_closed:
            await client.__aexit__(None, None, None)
        else:
            logger.info(
                "Skipping shared client cleanup during reinitialization because the client or owning loop is already closed"
            )
    except Exception as e:
        logger.error(f"Error during client reinitialization cleanup: {e}")


async def _initialize_shared_client(
    current_loop: asyncio.AbstractEventLoop,
    env_key: Optional[str],
) -> "OpenRouterClient":
    """Create, enter, and publish the shared OpenRouter client."""
    global _client_instance, _client_initialized, _client_loop

    # Import here to avoid circular dependency
    from .client.openrouter import OpenRouterClient

    api_key = env_key or get_required_env(EnvVars.API_KEY)

    logger.info("Initializing shared OpenRouterClient singleton")
    client = OpenRouterClient(
        api_key=api_key,
        base_url=get_env_value(EnvVars.BASE_URL, APIConfig.BASE_URL)
        or APIConfig.BASE_URL,
        app_name=get_env_value(EnvVars.APP_NAME),
        http_referer=get_env_value(EnvVars.HTTP_REFERER),
        enable_cache=True,
        cache_ttl=CacheConfig.DEFAULT_TTL_SECONDS,
    )
    _client_instance = client

    await client.__aenter__()

    _client_initialized = True
    _client_loop = current_loop
    logger.info("Shared OpenRouterClient initialized successfully")
    return client


async def get_shared_client() -> "OpenRouterClient":
    """
    Get or create the singleton OpenRouterClient instance.

    This function ensures that only one OpenRouterClient is created and shared
    across all handlers, preventing redundant AsyncClient creation and improving
    performance.

    Returns:
        OpenRouterClient: The shared client instance (already in context)

    Raises:
        ValueError: If OPENROUTER_API_KEY environment variable is not set

    Thread Safety:
        This function uses asyncio.Lock to ensure thread-safe initialization

    Note:
        The returned client is already in an async context manager, so handlers
        should NOT use 'async with client:' - just call client methods directly.
    """
    global _client_instance, _client_initialized, _client_loop

    current_loop = asyncio.get_running_loop()
    env_key = get_env_value(EnvVars.API_KEY)

    # Fast path: if already initialized, return immediately
    if _client_initialized and _client_instance is not None:
        reusable, _, _ = _inspect_shared_client_reuse(
            _client_instance,
            _client_loop,
            current_loop,
            env_key,
        )

        if reusable:
            return _client_instance

    # Slow path: acquire lock and initialize
    async with _get_client_lock():
        current_loop = asyncio.get_running_loop()
        env_key = get_env_value(EnvVars.API_KEY)

        # Double-check after acquiring lock (another coroutine might have initialized)
        if _client_initialized and _client_instance is not None:
            reusable, loop_closed, client_closed = _inspect_shared_client_reuse(
                _client_instance,
                _client_loop,
                current_loop,
                env_key,
            )

            if reusable:
                return _client_instance

            logger.info(
                "Reinitializing shared OpenRouterClient due to loop or key change"
            )
            try:
                await _cleanup_stale_shared_client(
                    _client_instance,
                    loop_closed=loop_closed,
                    client_closed=client_closed,
                )
            finally:
                _client_instance = None
                _client_initialized = False
                _client_loop = None

        return await _initialize_shared_client(current_loop, env_key)


async def get_openrouter_client() -> "OpenRouterClient":
    """Return the shared OpenRouter client (legacy helper for handlers/tests)."""
    return await get_shared_client()


async def cleanup_shared_client() -> None:
    """
    Clean up the shared client on shutdown.

    This should be called during application shutdown to properly close
    the HTTP client and release resources.
    """
    global _client_instance, _client_initialized, _client_loop

    if _client_instance is not None:
        logger.info("Cleaning up shared OpenRouterClient")
        try:
            if not _shared_client_is_closed(_client_instance):
                await _client_instance.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"Error during client cleanup: {e}")
        finally:
            _client_instance = None
            _client_initialized = False
            _client_loop = None


__all__ = ["mcp", "get_shared_client", "get_openrouter_client", "cleanup_shared_client"]
