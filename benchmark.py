#!/usr/bin/env python3
"""
Performance benchmark for OpenRouter MCP Server
"""

import asyncio
import time
from src.openrouter_mcp.models.cache import ModelCache


async def performance_benchmark():
    print('OpenRouter MCP Server - Performance Benchmark')
    print('=' * 50)
    
    cache = ModelCache(ttl_hours=1)
    
    # Test 1: Cold start (API + Enhancement)
    print('Test 1: Cold Start Performance')
    start = time.time()
    models = await cache.get_models(force_refresh=True)
    cold_time = time.time() - start
    print(f'   API fetch + enhancement: {cold_time:.2f}s')
    print(f'   Models loaded: {len(models)}')
    print(f'   Average per model: {(cold_time/len(models)*1000):.1f}ms')
    
    # Test 2: Memory cache performance
    print('\nTest 2: Memory Cache Performance')
    start = time.time()
    models = await cache.get_models()
    warm_time = time.time() - start
    print(f'   Memory cache access: {warm_time*1000:.1f}ms')
    print(f'   Speedup: {cold_time/warm_time:.0f}x faster')
    
    # Test 3: Filtering performance
    print('\nTest 3: Filtering Performance')
    
    filters = [
        ('Provider filter', {'provider': 'openai'}),
        ('Category filter', {'category': 'chat'}), 
        ('Capability filter', {'capabilities': {'supports_vision': True}}),
        ('Complex filter', {'provider': 'openai', 'performance_tier': 'premium', 'min_quality_score': 8.0}),
    ]
    
    for name, kwargs in filters:
        start = time.time()
        results = cache.filter_models_by_metadata(**kwargs)
        filter_time = time.time() - start
        print(f'   {name}: {filter_time*1000:.1f}ms ({len(results)} results)')
    
    # Test 4: Statistics performance
    print('\nTest 4: Statistics Performance')
    start = time.time()
    stats = cache.get_cache_stats()
    stats_time = time.time() - start
    print(f'   Cache stats: {stats_time*1000:.1f}ms')
    print(f'   Total providers: {len(stats["providers"])}')
    print(f'   Vision models: {stats["vision_capable_count"]}')
    print(f'   Cache size: {stats["cache_size_mb"]:.2f} MB')
    
    # Test 5: Metadata quality analysis
    print('\nTest 5: Metadata Quality Analysis')
    quality_scores = [m['quality_score'] for m in models]
    avg_quality = sum(quality_scores) / len(quality_scores)
    max_quality = max(quality_scores)
    
    tiers = cache.get_models_by_performance_tier()
    
    print(f'   Average quality score: {avg_quality:.1f}/10')
    print(f'   Maximum quality score: {max_quality:.1f}/10')
    print(f'   Premium models: {len(tiers["premium"])}')
    print(f'   Standard models: {len(tiers["standard"])}')
    print(f'   Economy models: {len(tiers["economy"])}')
    
    print('\nAll performance benchmarks completed successfully!')
    print('=' * 50)


if __name__ == "__main__":
    asyncio.run(performance_benchmark())