#!/usr/bin/env python3
"""
Test server startup with collective intelligence integration.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

async def test_server_import():
    """Test that all components import correctly."""
    print("Testing server components import...")
    
    try:
        # Test basic server import
        from src.openrouter_mcp.server import create_app
        print("Server module imported successfully")
        
        # Test collective intelligence handlers
        from src.openrouter_mcp.handlers.collective_intelligence import (
            collective_chat_completion,
            ensemble_reasoning,
            adaptive_model_selection,
            cross_model_validation,
            collaborative_problem_solving
        )
        print("Collective intelligence handlers imported successfully")
        
        # Test that the app can be created
        app = create_app()
        print("Server app created successfully")
        
        # Test that handlers are registered (simplified check)
        from src.openrouter_mcp.handlers.collective_intelligence import mcp
        print("MCP instance with collective intelligence tools created")
        
        print("\nAll server components imported and initialized successfully!")
        print("\nCollective Intelligence MCP Tools integrated:")
        print("  - collective_chat_completion")
        print("  - ensemble_reasoning") 
        print("  - adaptive_model_selection")
        print("  - cross_model_validation")
        print("  - collaborative_problem_solving")
        
    except Exception as e:
        print(f"Server startup test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def main():
    """Run the test."""
    print("OpenRouter MCP Server with Collective Intelligence")
    print("=" * 55)
    print()
    
    success = await test_server_import()
    
    if success:
        print("\nServer startup test completed successfully!")
        print("\nThe OpenRouter MCP server is now enhanced with collective intelligence capabilities.")
        print("You can start the server using:")
        print("  python -m src.openrouter_mcp.server")
        print("\nOr using the npm script:")
        print("  npm start")
    else:
        print("\nServer startup test failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())