#!/usr/bin/env python3
"""
Integration test script for MCP CLI commands.

This script demonstrates how to use the MCP CLI management system
to add, list, and manage MCP servers for Claude Code CLI.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from src.openrouter_mcp.cli.commands import add_mcp_server, get_mcp_server_status, list_mcp_servers


def test_mcp_cli_integration():
    """Test the MCP CLI commands in a real scenario."""

    print("🚀 Testing MCP CLI Integration")
    print("=" * 60)

    # Test 1: List servers (should be empty or show existing)
    print("\n1️⃣ Listing current MCP servers:")
    list_mcp_servers()

    # Test 2: Add OpenRouter server
    print("\n2️⃣ Adding OpenRouter MCP server:")
    api_key = os.getenv("OPENROUTER_API_KEY", "sk-or-test-key-123")
    success = add_mcp_server("openrouter", api_key=api_key, force=True)

    if success:
        print("✅ OpenRouter server added successfully!")
    else:
        print("❌ Failed to add OpenRouter server")
        assert False, "Failed to add OpenRouter server"

    # Test 3: List servers again (should show openrouter)
    print("\n3️⃣ Listing MCP servers after adding OpenRouter:")
    list_mcp_servers(verbose=True)

    # Test 4: Get status of OpenRouter server
    print("\n4️⃣ Getting status of OpenRouter server:")
    get_mcp_server_status("openrouter")

    # Test 5: Add another preset server (filesystem)
    print("\n5️⃣ Adding filesystem MCP server:")
    success = add_mcp_server("filesystem", directories=[str(Path.home() / "Desktop")], force=True)

    if success:
        print("✅ Filesystem server added successfully!")
    else:
        print("❌ Failed to add filesystem server")

    # Test 6: List all servers
    print("\n6️⃣ Final list of all MCP servers:")
    list_mcp_servers()

    print("\n" + "=" * 60)
    print("✅ MCP CLI Integration Test Complete!")
    print("\nNow you can use these commands in Claude Code CLI:")
    print("  export OPENROUTER_API_KEY=sk-or-...")
    print("  claude mcp add -s user openrouter -- npx @physics91/openrouter-mcp start")
    print("  claude mcp list")
    print("  claude mcp get openrouter")
    print("  claude mcp remove openrouter")


def demonstrate_cli_syntax():
    """Demonstrate the actual CLI command syntax."""

    print("\n" + "=" * 60)
    print("📚 Claude Code CLI - MCP Command Examples")
    print("=" * 60)

    examples = [
        ("Export API key", "export OPENROUTER_API_KEY=sk-or-xxx"),
        (
            "Add OpenRouter server",
            "claude mcp add -s user openrouter -- npx @physics91/openrouter-mcp start",
        ),
        (
            "Add project-scoped OpenRouter server",
            "claude mcp add -s project openrouter -- npx @physics91/openrouter-mcp start",
        ),
        ("List all servers", "claude mcp list"),
        ("Get server status", "claude mcp get openrouter"),
        ("Remove server", "claude mcp remove openrouter"),
        (
            "Custom server",
            "claude mcp add myserver -- python server.py --flag value",
        ),
    ]

    for description, command in examples:
        print(f"\n💡 {description}:")
        print(f"   $ {command}")

    print("\n" + "=" * 60)
    print("🎯 Available Presets:")
    from src.openrouter_mcp.cli.mcp_manager import MCPManager

    for preset in MCPManager.PRESETS.keys():
        print(f"   - {preset}")


def _configure_windows_utf8_stdio() -> Optional[Tuple[object, object]]:
    """Configure UTF-8 stdio for manual runs on Windows."""
    if sys.platform != "win32":
        return None

    import io

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        sys.stdout = io.TextIOWrapper(original_stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(original_stderr.buffer, encoding="utf-8")
    except Exception:
        # If stdout/stderr don't support buffer (e.g., pytest capture), leave unchanged
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        return None

    return original_stdout, original_stderr


if __name__ == "__main__":
    stdio_backup = _configure_windows_utf8_stdio()
    try:
        # Run the integration test
        success = test_mcp_cli_integration()

        # Show CLI examples
        demonstrate_cli_syntax()

        if not success:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if stdio_backup:
            sys.stdout, sys.stderr = stdio_backup
