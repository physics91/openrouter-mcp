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

import asyncio
import inspect
import logging
import signal
from typing import Any

from dotenv import load_dotenv

from .collective_intelligence import shutdown_lifecycle_manager
from .config.constants import EnvVars, LoggingConfig
from .handlers import register_handlers
from .mcp_registry import cleanup_shared_client, mcp
from .utils.env import get_env_value

logger = logging.getLogger(__name__)
_LOGGING_CONFIGURED = False


def configure_logging() -> None:
    """Configure server logging when the executable entrypoint runs."""
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        return

    logging.basicConfig(
        level=LoggingConfig.DEFAULT_LEVEL,
        format=LoggingConfig.FORMAT,
        datefmt=LoggingConfig.DATE_FORMAT,
    )
    _LOGGING_CONFIGURED = True


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


def create_app() -> Any:
    """Create and configure the FastMCP application."""
    load_dotenv()
    logger.info("Initializing OpenRouter MCP Server...")

    register_handlers()

    # Validate environment
    validate_environment()

    logger.info("OpenRouter MCP Server initialized successfully")

    return mcp


async def shutdown_handler() -> None:
    """Cleanup handler for server shutdown."""
    logger.info("Server shutdown initiated, cleaning up resources...")

    try:
        # Clean up shared OpenRouter client
        await cleanup_shared_client()
        logger.info("Shared OpenRouter client cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up shared client: {e}", exc_info=True)

    try:
        # Persist free model metrics before shutdown
        from .handlers.free_chat import _get_metrics_for_shutdown

        metrics = _get_metrics_for_shutdown()
        if metrics is not None:
            metrics.save()
            logger.info("Free model metrics saved successfully")
    except Exception as e:
        logger.error(f"Error saving free model metrics: {e}", exc_info=True)

    try:
        # Shutdown lifecycle manager
        await shutdown_lifecycle_manager()
        logger.info("Collective intelligence components shutdown successfully")
    except Exception as e:
        logger.error(f"Error during lifecycle manager shutdown: {e}", exc_info=True)


def _run_shutdown() -> None:
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


def main() -> None:
    """Main entry point for the server."""
    try:
        configure_logging()
        app = create_app()

        logger.info("Starting OpenRouter MCP Server via stdio")

        # Register shutdown handler for graceful cleanup
        def signal_handler(sig: int, frame: object) -> None:
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
