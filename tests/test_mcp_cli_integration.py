#!/usr/bin/env python3
"""
Integration test script for MCP CLI commands.

This script demonstrates how to use the MCP CLI management system
to add, list, and manage MCP servers for Claude Code CLI.
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

from src.openrouter_mcp.cli.commands import (
    add_mcp_server,
    list_mcp_servers,
    get_mcp_server_status,
    remove_mcp_server
)


def test_mcp_cli_integration():
    """Test the MCP CLI commands in a real scenario."""
    
    print("🚀 Testing MCP CLI Integration")
    print("=" * 60)
    
    # Test 1: List servers (should be empty or show existing)
    print("\n1️⃣ Listing current MCP servers:")
    servers = list_mcp_servers()
    
    # Test 2: Add OpenRouter server
    print("\n2️⃣ Adding OpenRouter MCP server:")
    api_key = os.getenv("OPENROUTER_API_KEY", "sk-or-test-key-123")
    success = add_mcp_server("openrouter", api_key=api_key, force=True)
    
    if success:
        print("✅ OpenRouter server added successfully!")
    else:
        print("❌ Failed to add OpenRouter server")
        return False
    
    # Test 3: List servers again (should show openrouter)
    print("\n3️⃣ Listing MCP servers after adding OpenRouter:")
    servers = list_mcp_servers(verbose=True)
    
    # Test 4: Get status of OpenRouter server
    print("\n4️⃣ Getting status of OpenRouter server:")
    status = get_mcp_server_status("openrouter")
    
    # Test 5: Add another preset server (filesystem)
    print("\n5️⃣ Adding filesystem MCP server:")
    success = add_mcp_server(
        "filesystem",
        directories=[str(Path.home() / "Desktop")],
        force=True
    )
    
    if success:
        print("✅ Filesystem server added successfully!")
    else:
        print("❌ Failed to add filesystem server")
    
    # Test 6: List all servers
    print("\n6️⃣ Final list of all MCP servers:")
    servers = list_mcp_servers()
    
    print("\n" + "=" * 60)
    print("✅ MCP CLI Integration Test Complete!")
    print("\nNow you can use these commands in Claude Code CLI:")
    print("  claude mcp add openrouter --api-key YOUR_KEY")
    print("  claude mcp list")
    print("  claude mcp status openrouter")
    print("  claude mcp remove openrouter")
    print("  claude mcp config openrouter --env OPENROUTER_API_KEY=NEW_KEY")
    
    return True


def demonstrate_cli_syntax():
    """Demonstrate the actual CLI command syntax."""
    
    print("\n" + "=" * 60)
    print("📚 Claude Code CLI - MCP Command Examples")
    print("=" * 60)
    
    examples = [
        ("Add OpenRouter server", "claude mcp add openrouter --api-key sk-or-xxx"),
        ("Add GitHub server", "claude mcp add github --token ghp_xxx"),
        ("Add filesystem server", "claude mcp add filesystem --args /path/to/dir"),
        ("List all servers", "claude mcp list"),
        ("List with details", "claude mcp list --verbose"),
        ("Get server status", "claude mcp status openrouter"),
        ("Update API key", "claude mcp config openrouter --env OPENROUTER_API_KEY=new-key"),
        ("Remove server", "claude mcp remove openrouter"),
        ("Force add (overwrite)", "claude mcp add openrouter --api-key xxx --force"),
        ("Custom server", "claude mcp add myserver --command python --args server.py --cwd /project"),
    ]
    
    for description, command in examples:
        print(f"\n💡 {description}:")
        print(f"   $ {command}")
    
    print("\n" + "=" * 60)
    print("🎯 Available Presets:")
    from src.openrouter_mcp.cli.mcp_manager import MCPManager
    for preset in MCPManager.PRESETS.keys():
        print(f"   - {preset}")


if __name__ == "__main__":
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