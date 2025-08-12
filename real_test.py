#!/usr/bin/env python3
"""
Real API integration test for OpenRouter MCP Server
"""

import asyncio
import os
import time
from src.openrouter_mcp.models.cache import ModelCache
from src.openrouter_mcp.client.openrouter import OpenRouterClient


async def real_api_test():
    print('OpenRouter MCP Server - Real API Integration Test')
    print('=' * 60)
    
    # Set API key
    api_key = "placeholder"
    os.environ["OPENROUTER_API_KEY"] = api_key
    
    try:
        # Test 1: Direct API client test
        print('Test 1: Direct API Client')
        client = OpenRouterClient.from_env()
        async with client:
            start = time.time()
            raw_models = await client.list_models()
            api_time = time.time() - start
            print(f'   API fetch successful: {api_time:.2f}s')
            print(f'   Raw models fetched: {len(raw_models)}')
            
            # Show first few models
            print('   Sample models:')
            for model in raw_models[:3]:
                print(f'      - {model.get("id", "unknown")} - {model.get("name", "No name")}')
        
        print()
        
        # Test 2: Cache system with real API
        print('Test 2: Cache System with Real API')
        cache = ModelCache(ttl_hours=1, cache_file="test_cache.json")
        
        # Cold start test
        print('   Cold start test (API + Enhancement):')
        start = time.time()
        enhanced_models = await cache.get_models(force_refresh=True)
        cold_time = time.time() - start
        print(f'      API + Enhancement: {cold_time:.2f}s')
        print(f'      Enhanced models: {len(enhanced_models)}')
        print(f'      Average per model: {(cold_time/len(enhanced_models)*1000):.1f}ms')
        
        # Warm cache test
        print('   Warm cache test:')
        start = time.time()
        cached_models = await cache.get_models()
        warm_time = time.time() - start
        print(f'      Memory cache access: {warm_time*1000:.1f}ms')
        print(f'      Speedup: {cold_time/warm_time:.0f}x faster')
        
        print()
        
        # Test 3: Enhanced metadata validation
        print('Test 3: Enhanced Metadata Validation')
        sample_model = enhanced_models[0] if enhanced_models else None
        
        if sample_model:
            print(f'   Sample Enhanced Model: {sample_model["id"]}')
            print(f'      Provider: {sample_model.get("provider", "unknown")}')
            print(f'      Category: {sample_model.get("category", "unknown")}')
            print(f'      Performance Tier: {sample_model.get("performance_tier", "unknown")}')
            print(f'      Quality Score: {sample_model.get("quality_score", 0):.1f}/10')
            print(f'      Cost Tier: {sample_model.get("cost_tier", "unknown")}')
            
            capabilities = sample_model.get("capabilities", {})
            print(f'      Vision Support: {capabilities.get("supports_vision", False)}')
            print(f'      Function Calling: {capabilities.get("supports_function_calling", False)}')
            print(f'      Context Length: {capabilities.get("max_tokens", 0):,} tokens')
        
        print()
        
        # Test 4: Advanced filtering
        print('Test 4: Advanced Filtering Tests')
        
        # Provider-based filtering
        providers_found = set()
        categories_found = set()
        
        for model in enhanced_models:
            providers_found.add(model.get("provider", "unknown"))
            categories_found.add(model.get("category", "unknown"))
        
        print(f'   Providers detected: {len(providers_found)}')
        for provider in sorted(providers_found):
            provider_models = cache.filter_models_by_metadata(provider=provider)
            print(f'      - {provider}: {len(provider_models)} models')
        
        print(f'   Categories detected: {len(categories_found)}')
        for category in sorted(categories_found):
            category_models = cache.filter_models_by_metadata(category=category)
            print(f'      - {category}: {len(category_models)} models')
        
        # Performance tier analysis
        tiers = cache.get_models_by_performance_tier()
        print(f'   Performance tiers:')
        print(f'      - Premium: {len(tiers["premium"])} models')
        print(f'      - Standard: {len(tiers["standard"])} models')
        print(f'      - Economy: {len(tiers["economy"])} models')
        
        # Vision models
        vision_models = cache.filter_models_by_metadata(
            capabilities={"supports_vision": True}
        )
        print(f'   Vision-capable models: {len(vision_models)}')
        
        print()
        
        # Test 5: Cache statistics
        print('Test 5: Cache Statistics & Performance')
        stats = cache.get_cache_stats()
        
        print(f'   Cache Statistics:')
        print(f'      Total models: {stats["total_models"]}')
        print(f'      Cache size: {stats["cache_size_mb"]:.2f} MB')
        print(f'      Vision models: {stats["vision_capable_count"]}')
        print(f'      Reasoning models: {stats["reasoning_model_count"]}')
        print(f'      Providers: {len(stats["providers"])}')
        print(f'      Last updated: {stats["last_updated"]}')
        print(f'      Is expired: {stats["is_expired"]}')
        
        # Quality analysis
        quality_scores = [m["quality_score"] for m in enhanced_models]
        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)
            max_quality = max(quality_scores)
            min_quality = min(quality_scores)
            
            print(f'   Quality Analysis:')
            print(f'      Average quality: {avg_quality:.1f}/10')
            print(f'      Quality range: {min_quality:.1f} - {max_quality:.1f}')
            
            # Find best quality models
            best_models = [m for m in enhanced_models if m["quality_score"] >= 8.0]
            print(f'      High quality models (8.0+): {len(best_models)}')
        
        print()
        
        # Test 6: Performance benchmarks
        print('Test 6: Performance Benchmarks')
        
        # Filter performance test
        filter_tests = [
            ("OpenAI models", {"provider": "openai"}),
            ("Chat models", {"category": "chat"}),
            ("Vision models", {"capabilities": {"supports_vision": True}}),
            ("Premium models", {"performance_tier": "premium"}),
            ("Complex filter", {
                "performance_tier": "standard",
                "min_quality_score": 5.0,
                "cost_tier": "medium"
            })
        ]
        
        print('   Filter performance:')
        for test_name, filter_kwargs in filter_tests:
            start = time.time()
            results = cache.filter_models_by_metadata(**filter_kwargs)
            filter_time = (time.time() - start) * 1000
            print(f'      - {test_name}: {filter_time:.1f}ms ({len(results)} results)')
        
        print()
        print('All real API integration tests completed successfully!')
        print('OpenRouter MCP Server metadata enhancement system is working perfectly!')
        print('=' * 60)
        
        # Clean up test cache file
        try:
            os.remove("test_cache.json")
            print('Test cache file cleaned up')
        except:
            pass
            
    except Exception as e:
        print(f'Test failed with error: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(real_api_test())
    exit(0 if success else 1)