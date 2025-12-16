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
    - All handlers must import 'mcp' and 'get_shared_client' from this module

Usage:
    from openrouter_mcp.mcp_registry import mcp, get_shared_client

    @mcp.tool()
    async def my_tool(...):
        client = await get_shared_client()
        # Use client without async context manager (already managed)
        result = await client.list_models()
"""

import os
import logging
import asyncio
from typing import Optional
from fastmcp import FastMCP

from .config.constants import APIConfig, CacheConfig, EnvVars

logger = logging.getLogger(__name__)

# Create the single shared FastMCP instance
# This instance will be used by all handlers for tool registration
mcp = FastMCP("openrouter-mcp")

# Singleton client instance and lock for thread-safe initialization
_client_instance: Optional[object] = None  # Will be OpenRouterClient
_client_lock = asyncio.Lock()
_client_initialized = False


async def get_shared_client():
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
    global _client_instance, _client_initialized

    # Fast path: if already initialized, return immediately
    if _client_initialized and _client_instance is not None:
        return _client_instance

    # Slow path: acquire lock and initialize
    async with _client_lock:
        # Double-check after acquiring lock (another coroutine might have initialized)
        if _client_initialized and _client_instance is not None:
            return _client_instance

        # Import here to avoid circular dependency
        from .client.openrouter import OpenRouterClient

        # Get API key
        api_key = os.getenv(EnvVars.API_KEY)
        if not api_key:
            raise ValueError(f"{EnvVars.API_KEY} environment variable is required")

        # Create client with environment configuration
        logger.info("Initializing shared OpenRouterClient singleton")
        _client_instance = OpenRouterClient(
            api_key=api_key,
            base_url=os.getenv(EnvVars.BASE_URL, APIConfig.BASE_URL),
            app_name=os.getenv(EnvVars.APP_NAME),
            http_referer=os.getenv(EnvVars.HTTP_REFERER),
            enable_cache=True,
            cache_ttl=CacheConfig.DEFAULT_TTL_SECONDS
        )

        # Enter the async context manager once
        await _client_instance.__aenter__()

        _client_initialized = True
        logger.info("Shared OpenRouterClient initialized successfully")

        return _client_instance


async def cleanup_shared_client():
    """
    Clean up the shared client on shutdown.

    This should be called during application shutdown to properly close
    the HTTP client and release resources.
    """
    global _client_instance, _client_initialized

    if _client_instance is not None:
        logger.info("Cleaning up shared OpenRouterClient")
        try:
            await _client_instance.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"Error during client cleanup: {e}")
        finally:
            _client_instance = None
            _client_initialized = False


__all__ = ["mcp", "get_shared_client", "cleanup_shared_client"]
