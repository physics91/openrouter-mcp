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
from typing import TYPE_CHECKING, Optional

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
        loop_matches = _client_loop is None or _client_loop is current_loop
        loop_closed = _client_loop.is_closed() if _client_loop is not None else False
        key_matches = (not env_key) or (getattr(_client_instance, "api_key", None) == env_key)

        if loop_matches and not loop_closed and key_matches:
            return _client_instance

    # Slow path: acquire lock and initialize
    async with _get_client_lock():
        current_loop = asyncio.get_running_loop()
        env_key = get_env_value(EnvVars.API_KEY)

        # Double-check after acquiring lock (another coroutine might have initialized)
        if _client_initialized and _client_instance is not None:
            loop_matches = _client_loop is None or _client_loop is current_loop
            loop_closed = _client_loop.is_closed() if _client_loop is not None else False
            key_matches = (not env_key) or (getattr(_client_instance, "api_key", None) == env_key)

            if loop_matches and not loop_closed and key_matches:
                return _client_instance

            logger.info("Reinitializing shared OpenRouterClient due to loop or key change")
            try:
                await _client_instance.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error during client reinitialization cleanup: {e}")
            finally:
                _client_instance = None
                _client_initialized = False
                _client_loop = None

        # Import here to avoid circular dependency
        from .client.openrouter import OpenRouterClient

        # Get API key
        api_key = env_key or get_required_env(EnvVars.API_KEY)

        # Create client with environment configuration
        logger.info("Initializing shared OpenRouterClient singleton")
        _client_instance = OpenRouterClient(
            api_key=api_key,
            base_url=get_env_value(EnvVars.BASE_URL, APIConfig.BASE_URL) or APIConfig.BASE_URL,
            app_name=get_env_value(EnvVars.APP_NAME),
            http_referer=get_env_value(EnvVars.HTTP_REFERER),
            enable_cache=True,
            cache_ttl=CacheConfig.DEFAULT_TTL_SECONDS,
        )

        # Enter the async context manager once
        await _client_instance.__aenter__()

        _client_initialized = True
        _client_loop = current_loop
        logger.info("Shared OpenRouterClient initialized successfully")

    return _client_instance


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
            await _client_instance.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"Error during client cleanup: {e}")
        finally:
            _client_instance = None
            _client_initialized = False
            _client_loop = None


__all__ = ["mcp", "get_shared_client", "get_openrouter_client", "cleanup_shared_client"]
