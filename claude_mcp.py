#!/usr/bin/env python3
"""
Claude MCP - Command-line interface for managing MCP servers in Claude Code.

This script provides a standalone CLI for managing MCP servers that can be
integrated with Claude Code CLI or used independently.

Usage:
    python claude_mcp.py add openrouter --api-key YOUR_KEY
    python claude_mcp.py list
    python claude_mcp.py status openrouter
    python claude_mcp.py remove openrouter
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add the project to the path
sys.path.insert(0, str(Path(__file__).parent))

# Import the CLI command group
from src.openrouter_mcp.cli.commands import mcp

if __name__ == "__main__":
    # Run the Click CLI
    mcp()