#!/usr/bin/env python3
"""
Debug test to understand why only 1 model is returned
"""

import asyncio
import os
import logging
from src.openrouter_mcp.client.openrouter import OpenRouterClient
from src.openrouter_mcp.models.cache import ModelCache

# Set up debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_api_fetch():
    print('Debug: API Fetch Analysis')
    print('=' * 40)
    
    # Set API key
    os.environ["OPENROUTER_API_KEY"] = "placeholder"
    
    try:
        # Test 1: Direct client call
        print('\n1. Direct client test:')
        client = OpenRouterClient.from_env()
        async with client:
            models = await client.list_models()
            print(f'   Direct client returned: {len(models)} models')
            if models:
                print(f'   First model: {models[0].get("id", "unknown")}')
                print(f'   Last model: {models[-1].get("id", "unknown")}')
        
        # Test 2: Cache system
        print('\n2. Cache system test:')
        cache = ModelCache(ttl_hours=1, cache_file="debug_cache.json")
        
        # Clear any existing cache
        cache._memory_cache = []
        cache._last_update = None
        
        cached_models = await cache.get_models(force_refresh=True)
        print(f'   Cache system returned: {len(cached_models)} models')
        if cached_models:
            print(f'   First cached model: {cached_models[0].get("id", "unknown")}')
            
        # Test 3: Check what's happening in _fetch_models_from_api
        print('\n3. Direct _fetch_models_from_api test:')
        direct_models = await cache._fetch_models_from_api()
        print(f'   _fetch_models_from_api returned: {len(direct_models)} models')
        
        # Clean up
        try:
            os.remove("debug_cache.json")
        except:
            pass
            
    except Exception as e:
        print(f'Debug test failed: {e}')
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_api_fetch())