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
from typing import Any
from pathlib import Path

import uvicorn
from fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Import handlers to register MCP tools
try:
    from .handlers import chat  # noqa: F401
    from .handlers import multimodal  # noqa: F401
    from .handlers import mcp_benchmark  # noqa: F401
    from .handlers import collective_intelligence  # noqa: F401
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from openrouter_mcp.handlers import chat  # noqa: F401
    from openrouter_mcp.handlers import multimodal  # noqa: F401
    from openrouter_mcp.handlers import mcp_benchmark  # noqa: F401
    from openrouter_mcp.handlers import collective_intelligence  # noqa: F401


def validate_environment() -> None:
    """Validate that required environment variables are set."""
    required_vars = ["OPENROUTER_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your .env file or environment")
        raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    logger.info("Environment validation successful")


# Create FastMCP instance
mcp = FastMCP("openrouter-mcp")


def create_app():
    """Create and configure the FastMCP application."""
    logger.info("Initializing OpenRouter MCP Server...")
    
    # Validate environment
    validate_environment()
    
    logger.info("OpenRouter MCP Server initialized successfully")
    
    return mcp


def main():
    """Main entry point for the server."""
    try:
        app = create_app()
        
        logger.info("Starting OpenRouter MCP Server via stdio")
        
        # Start the FastMCP server in stdio mode
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}")
        raise


if __name__ == "__main__":
    main()