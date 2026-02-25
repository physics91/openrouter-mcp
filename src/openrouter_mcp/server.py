#!/usr/bin/env python3

"""
OpenRouter MCP Server

A Model Context Protocol (MCP) server that provides access to OpenRouter's AI models.
This server enables seamless integration with various AI models through OpenRouter's API,
offering capabilities like chat completion, model listing, and usage tracking.

Features:
- Chat with multiple AI models (GPT-4, Claude, Llama, etc.)
- List available models with pricing and capabilities
- Track API usage and costs
- Support for streaming responses
- Built with FastMCP for high performance

Usage:
    Set your OpenRouter API key in the OPENROUTER_API_KEY environment variable,
    then run this server with FastMCP.
"""

import os
import logging
import signal
import asyncio
import inspect
from typing import Any
from pathlib import Path

import uvicorn
from fastmcp import FastMCP
from dotenv import load_dotenv
from .config.constants import EnvVars, LoggingConfig
from .utils.env import get_env_value

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=LoggingConfig.DEFAULT_LEVEL,
    format=LoggingConfig.FORMAT,
    datefmt=LoggingConfig.DATE_FORMAT,
)

logger = logging.getLogger(__name__)

# Import shared MCP instance from registry
# This must be imported before handlers to ensure proper registration
try:
    from .mcp_registry import mcp, cleanup_shared_client
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from openrouter_mcp.mcp_registry import mcp, cleanup_shared_client

# Import handlers to register MCP tools
# These imports trigger the @mcp.tool() decorators which register tools with the shared instance
try:
    from .handlers import chat  # noqa: F401
    from .handlers import multimodal  # noqa: F401
    from .handlers import mcp_benchmark  # noqa: F401
    from .handlers import collective_intelligence  # noqa: F401
    from .handlers import free_chat  # noqa: F401
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from openrouter_mcp.handlers import chat  # noqa: F401
    from openrouter_mcp.handlers import multimodal  # noqa: F401
    from openrouter_mcp.handlers import mcp_benchmark  # noqa: F401
    from openrouter_mcp.handlers import collective_intelligence  # noqa: F401
    from openrouter_mcp.handlers import free_chat  # noqa: F401

# Import lifecycle shutdown at module level for patching in tests
try:
    from .collective_intelligence import shutdown_lifecycle_manager
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from openrouter_mcp.collective_intelligence import shutdown_lifecycle_manager


def validate_environment() -> None:
    """Validate that required environment variables are set."""
    required_vars = [EnvVars.API_KEY]
    missing_vars = []

    for var in required_vars:
        if not get_env_value(var):
            missing_vars.append(var)

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your .env file or environment")
        raise ValueError(f"Missing required environment variables: {missing_vars}")

    logger.info("Environment validation successful")


def create_app():
    """Create and configure the FastMCP application."""
    logger.info("Initializing OpenRouter MCP Server...")
    
    # Validate environment
    validate_environment()
    
    logger.info("OpenRouter MCP Server initialized successfully")
    
    return mcp


async def shutdown_handler():
    """Cleanup handler for server shutdown."""
    logger.info("Server shutdown initiated, cleaning up resources...")

    try:
        # Clean up shared OpenRouter client
        await cleanup_shared_client()
        logger.info("Shared OpenRouter client cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up shared client: {e}", exc_info=True)

    try:
        # Shutdown lifecycle manager
        await shutdown_lifecycle_manager()
        logger.info("Collective intelligence components shutdown successfully")
    except Exception as e:
        logger.error(f"Error during lifecycle manager shutdown: {e}", exc_info=True)


def _run_shutdown():
    """Run shutdown handler safely, avoiding un-awaited coroutine warnings."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        loop.create_task(shutdown_handler())
    else:
        coro = shutdown_handler()
        try:
            asyncio.run(coro)
        finally:
            if inspect.iscoroutine(coro):
                coro.close()


def main():
    """Main entry point for the server."""
    try:
        app = create_app()

        logger.info("Starting OpenRouter MCP Server via stdio")

        # Register shutdown handler for graceful cleanup
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            raise KeyboardInterrupt()

        # Register signal handlers for clean shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start the FastMCP server in stdio mode
        try:
            app.run()
        finally:
            # Ensure cleanup runs even if run() exits normally
            logger.info("Server stopped, running final cleanup...")
            _run_shutdown()

    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}")
        raise


if __name__ == "__main__":
    main()
