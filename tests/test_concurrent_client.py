#!/usr/bin/env python3
"""
Test concurrent client access and file locking.

This test verifies that:
1. Multiple concurrent calls share the same OpenRouterClient instance
2. File locking prevents cache corruption during concurrent writes
3. The singleton pattern works correctly across async operations
"""

import pytest
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture(autouse=True)
def _set_test_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")


@pytest.mark.asyncio
async def test_shared_client_singleton():
    """Test that get_shared_client returns the same instance across calls."""
    from openrouter_mcp.mcp_registry import get_shared_client, cleanup_shared_client

    try:
        # Get client multiple times
        client1 = await get_shared_client()
        client2 = await get_shared_client()
        client3 = await get_shared_client()

        # All should be the same instance
        assert client1 is client2
        assert client2 is client3
        assert id(client1) == id(client2) == id(client3)

    finally:
        # Clean up
        await cleanup_shared_client()


@pytest.mark.asyncio
async def test_concurrent_client_access():
    """Test that concurrent handler calls share the same client."""
    from openrouter_mcp.mcp_registry import get_shared_client, cleanup_shared_client

    try:
        # Simulate concurrent access from multiple handlers
        async def simulate_handler_call(handler_id: int):
            client = await get_shared_client()
            return id(client), handler_id

        # Run 10 concurrent simulated handler calls
        tasks = [simulate_handler_call(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should have the same client ID
        client_ids = [result[0] for result in results]
        assert len(set(client_ids)) == 1, "All handlers should share the same client instance"

    finally:
        await cleanup_shared_client()


@pytest.mark.asyncio
async def test_file_locking_prevents_corruption():
    """Test that file locking prevents concurrent write corruption."""
    from openrouter_mcp.models.cache import ModelCache
    import json

    # Create temporary cache file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_file = f.name

    try:
        # Create multiple cache instances pointing to the same file
        cache1 = ModelCache(ttl_hours=1.0, cache_file=cache_file, api_key="test-key")
        cache2 = ModelCache(ttl_hours=1.0, cache_file=cache_file, api_key="test-key")
        cache3 = ModelCache(ttl_hours=1.0, cache_file=cache_file, api_key="test-key")

        # Test data
        models1 = [{"id": "model1", "name": "Model 1"}]
        models2 = [{"id": "model2", "name": "Model 2"}]
        models3 = [{"id": "model3", "name": "Model 3"}]

        # Concurrent writes should not corrupt the file
        async def write_models(cache, models):
            # Simulate some processing time
            await asyncio.sleep(0.01)
            cache._save_to_file_cache(models)
            await asyncio.sleep(0.01)

        # Run concurrent writes
        await asyncio.gather(
            write_models(cache1, models1),
            write_models(cache2, models2),
            write_models(cache3, models3)
        )

        # File should still be valid JSON (not corrupted)
        with open(cache_file, 'r') as f:
            data = json.load(f)

        # Verify structure is intact
        assert "models" in data
        assert "updated_at" in data
        assert isinstance(data["models"], list)

        # One of the writes should have succeeded
        assert len(data["models"]) > 0

    finally:
        # Clean up
        if os.path.exists(cache_file):
            os.unlink(cache_file)


@pytest.mark.asyncio
async def test_concurrent_cache_read_write():
    """Test concurrent reads and writes to cache file."""
    from openrouter_mcp.models.cache import ModelCache
    import json

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_file = f.name
        # Initialize with some data
        json.dump({
            "models": [{"id": "initial", "name": "Initial Model"}],
            "updated_at": "2025-01-01T00:00:00"
        }, f)

    try:
        cache = ModelCache(ttl_hours=1.0, cache_file=cache_file, api_key="test-key")

        read_count = 0
        write_count = 0

        async def reader(reader_id: int):
            nonlocal read_count
            for _ in range(5):
                models, updated = cache._load_from_file_cache()
                if models:
                    read_count += 1
                await asyncio.sleep(0.005)

        async def writer(writer_id: int):
            nonlocal write_count
            for i in range(3):
                models = [{"id": f"writer{writer_id}_model{i}", "name": f"Writer {writer_id} Model {i}"}]
                cache._save_to_file_cache(models)
                write_count += 1
                await asyncio.sleep(0.01)

        # Run concurrent readers and writers
        tasks = (
            [reader(i) for i in range(3)] +
            [writer(i) for i in range(2)]
        )
        await asyncio.gather(*tasks)

        # Verify we had successful reads and writes
        assert read_count > 0, "Should have successful reads"
        assert write_count > 0, "Should have successful writes"

        # Final file should still be valid
        with open(cache_file, 'r') as f:
            data = json.load(f)
        assert "models" in data
        assert isinstance(data["models"], list)

    finally:
        if os.path.exists(cache_file):
            os.unlink(cache_file)


@pytest.mark.asyncio
async def test_client_cleanup():
    """Test that client cleanup works properly."""
    from openrouter_mcp.mcp_registry import (
        get_shared_client,
        cleanup_shared_client,
        _client_instance,
        _client_initialized
    )

    # Get client
    client = await get_shared_client()
    assert client is not None

    # Clean up
    await cleanup_shared_client()

    # Should be able to get a new client after cleanup
    new_client = await get_shared_client()
    assert new_client is not None

    # Final cleanup
    await cleanup_shared_client()


@pytest.mark.asyncio
async def test_handlers_use_shared_client():
    """Test that handlers actually use the shared client (integration test)."""
    from openrouter_mcp.handlers.chat import get_openrouter_client as chat_get_client
    from openrouter_mcp.handlers.multimodal import get_openrouter_client as multimodal_get_client
    from openrouter_mcp.mcp_registry import cleanup_shared_client

    try:
        # Get clients from different handlers
        chat_client = await chat_get_client()
        multimodal_client = await multimodal_get_client()

        # Should be the same instance
        assert chat_client is multimodal_client
        assert id(chat_client) == id(multimodal_client)

    finally:
        await cleanup_shared_client()


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_shared_client_singleton())
    print("✓ test_shared_client_singleton passed")

    asyncio.run(test_concurrent_client_access())
    print("✓ test_concurrent_client_access passed")

    asyncio.run(test_file_locking_prevents_corruption())
    print("✓ test_file_locking_prevents_corruption passed")

    asyncio.run(test_concurrent_cache_read_write())
    print("✓ test_concurrent_cache_read_write passed")

    asyncio.run(test_client_cleanup())
    print("✓ test_client_cleanup passed")

    asyncio.run(test_handlers_use_shared_client())
    print("✓ test_handlers_use_shared_client passed")

    print("\n✓ All tests passed!")
