#!/usr/bin/env python3
"""
Tests for dynamic model caching and updating functionality.

This test suite follows TDD principles to implement model caching system
that keeps the latest AI models from OpenRouter API.
"""

import pytest
import time
import json
import tempfile
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime, timedelta
from pathlib import Path


class TestModelCache:
    """Test dynamic model caching system - TDD RED phase."""

    @pytest.fixture
    def mock_openrouter_models(self):
        """Mock OpenRouter API response with latest 2025 models."""
        return {
            "data": [
                {
                    "id": "openai/gpt-5",
                    "name": "GPT-5",
                    "description": "OpenAI's most advanced model with enhanced reasoning",
                    "context_length": 200000,
                    "architecture": {
                        "modality": "text",
                        "tokenizer": "cl100k_base",
                        "instruct_type": "chatml"
                    },
                    "pricing": {
                        "prompt": "0.000005",
                        "completion": "0.000015"
                    },
                    "top_provider": {
                        "provider": "OpenAI"
                    }
                },
                {
                    "id": "anthropic/claude-4",
                    "name": "Claude 4",
                    "description": "Anthropic's breakthrough AI with improved reliability",
                    "context_length": 200000,
                    "architecture": {
                        "modality": "text",
                        "tokenizer": "claude",
                        "instruct_type": "claude"
                    },
                    "pricing": {
                        "prompt": "0.000015",
                        "completion": "0.000075"
                    },
                    "top_provider": {
                        "provider": "Anthropic"
                    }
                },
                {
                    "id": "google/gemini-2-5-pro",
                    "name": "Gemini 2.5 Pro",
                    "description": "Google's advanced multimodal AI with 1M+ context",
                    "context_length": 1000000,
                    "architecture": {
                        "modality": "text+image",
                        "tokenizer": "gemini",
                        "instruct_type": "gemini"
                    },
                    "pricing": {
                        "prompt": "0.0000025",
                        "completion": "0.00001"
                    },
                    "top_provider": {
                        "provider": "Google"
                    }
                },
                {
                    "id": "deepseek/deepseek-v3",
                    "name": "DeepSeek V3",
                    "description": "671B parameter MoE model with 37B active parameters",
                    "context_length": 128000,
                    "architecture": {
                        "modality": "text",
                        "tokenizer": "deepseek",
                        "instruct_type": "chatml"
                    },
                    "pricing": {
                        "prompt": "0.000001",
                        "completion": "0.000002"
                    },
                    "top_provider": {
                        "provider": "DeepSeek"
                    }
                },
                {
                    "id": "openai/o1",
                    "name": "OpenAI o1",
                    "description": "Advanced reasoning model for complex tasks",
                    "context_length": 128000,
                    "architecture": {
                        "modality": "text",
                        "tokenizer": "o200k_base",
                        "instruct_type": "chatml"
                    },
                    "pricing": {
                        "prompt": "0.000015",
                        "completion": "0.00006"
                    },
                    "top_provider": {
                        "provider": "OpenAI"
                    }
                }
            ]
        }

    @pytest.fixture
    def cache_config(self):
        """Configuration for model cache."""
        return {
            "ttl_hours": 1,
            "max_memory_items": 1000,
            "cache_file": "test_model_cache.json"
        }

    def test_model_cache_initialization(self, cache_config):
        """Test that model cache initializes properly."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        assert cache.ttl_seconds == 3600  # 1 hour
        assert cache.max_memory_items == 1000
        assert cache.cache_file == "test_model_cache.json"
        assert cache._memory_cache == []  # Memory cache is a list, not dict
        assert cache._last_update is None

    def test_cache_is_expired_initially(self, cache_config):
        """Test that cache is considered expired initially."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        assert cache.is_expired() == True

    def test_cache_expiry_logic(self, cache_config):
        """Test cache expiry based on TTL."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        # Simulate cache update
        cache._last_update = datetime.now()
        assert cache.is_expired() == False
        
        # Simulate expired cache
        cache._last_update = datetime.now() - timedelta(hours=2)
        assert cache.is_expired() == True

    @pytest.mark.asyncio
    async def test_fetch_models_from_api(self, mock_openrouter_models, cache_config):
        """Test fetching models from OpenRouter API."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        with patch('src.openrouter_mcp.client.openrouter.OpenRouterClient.from_env') as mock_client_getter:
            mock_client = MagicMock()
            mock_client_getter.return_value = mock_client
            
            async def mock_aenter(self):
                return mock_client
                
            async def mock_aexit(self, *args):
                return None
                
            mock_client.__aenter__ = mock_aenter
            mock_client.__aexit__ = mock_aexit
            async def mock_list_models():
                return mock_openrouter_models["data"]
            mock_client.list_models = mock_list_models
            
            models = await cache._fetch_models_from_api()
            
            assert len(models) == 5
            assert models[0]["id"] == "openai/gpt-5"
            assert models[1]["id"] == "anthropic/claude-4"
            assert models[2]["id"] == "google/gemini-2-5-pro"
            # Verify the mock was called (no direct assert for function)

    def test_save_to_file_cache(self, mock_openrouter_models, cache_config):
        """Test saving models to file cache."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        models = mock_openrouter_models["data"]
        
        with patch('builtins.open', mock_open()) as mock_file:
            cache._save_to_file_cache(models)
            
            mock_file.assert_called_once_with(cache_config["cache_file"], 'w', encoding='utf-8')
            # Verify JSON was written
            handle = mock_file()
            written_data = ''.join(call[0][0] for call in handle.write.call_args_list)
            saved_data = json.loads(written_data)
            
            assert "models" in saved_data
            assert "updated_at" in saved_data
            assert len(saved_data["models"]) == 5

    def test_load_from_file_cache_success(self, mock_openrouter_models, cache_config):
        """Test loading models from file cache when file exists."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        # Mock file content
        cache_data = {
            "models": mock_openrouter_models["data"],
            "updated_at": datetime.now().isoformat()
        }
        mock_file_content = json.dumps(cache_data)
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            with patch('pathlib.Path.exists', return_value=True):
                models, last_update = cache._load_from_file_cache()
                
                assert len(models) == 5
                assert models[0]["id"] == "openai/gpt-5"
                assert last_update is not None

    def test_load_from_file_cache_file_not_exists(self, cache_config):
        """Test loading from file cache when file doesn't exist."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        with patch('pathlib.Path.exists', return_value=False):
            models, last_update = cache._load_from_file_cache()
            
            assert models == []
            assert last_update is None

    @pytest.mark.asyncio
    async def test_get_models_cache_hit(self, mock_openrouter_models, cache_config):
        """Test getting models when cache is valid (cache hit)."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        # Simulate valid cache
        cache._memory_cache = mock_openrouter_models["data"]
        cache._last_update = datetime.now()
        
        models = await cache.get_models()
        
        assert len(models) == 5
        assert models[0]["id"] == "openai/gpt-5"

    @pytest.mark.asyncio
    async def test_get_models_cache_miss(self, mock_openrouter_models, cache_config):
        """Test getting models when cache is expired (cache miss)."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        with patch('src.openrouter_mcp.client.openrouter.OpenRouterClient.from_env') as mock_client_getter:
            mock_client = MagicMock()
            mock_client_getter.return_value = mock_client
            
            async def mock_aenter(self):
                return mock_client
                
            async def mock_aexit(self, *args):
                return None
                
            mock_client.__aenter__ = mock_aenter
            mock_client.__aexit__ = mock_aexit
            async def mock_list_models():
                return mock_openrouter_models["data"]
            mock_client.list_models = mock_list_models
            
            with patch.object(cache, '_save_to_file_cache') as mock_save:
                models = await cache.get_models()
                
                assert len(models) == 5
                assert models[0]["id"] == "openai/gpt-5"
                mock_save.assert_called_once()
                # Cache should have enhanced models, not raw data
                assert len(cache._memory_cache) == 5
                # Check that models are enhanced with metadata
                assert "provider" in cache._memory_cache[0]
                assert "category" in cache._memory_cache[0]

    def test_get_model_metadata(self, mock_openrouter_models, cache_config):
        """Test extracting enhanced model metadata."""
        from src.openrouter_mcp.models.cache import ModelCache
        from src.openrouter_mcp.utils.metadata import batch_enhance_models
        
        cache = ModelCache(**cache_config)
        # Enhance models before adding to cache (mimics what happens in _fetch_models_from_api)
        cache._memory_cache = batch_enhance_models(mock_openrouter_models["data"])
        
        # Test GPT-5 metadata
        gpt5_meta = cache.get_model_metadata("openai/gpt-5")
        assert gpt5_meta["provider"] == "openai"  # lowercase after enhancement
        assert gpt5_meta["capabilities"]["supports_vision"] == False
        assert gpt5_meta["context_length"] == 200000
        
        # Test Gemini multimodal metadata
        gemini_meta = cache.get_model_metadata("google/gemini-2-5-pro")
        assert gemini_meta["provider"] == "google"  # lowercase after enhancement
        # Gemini has text+image modality, so should support vision
        assert gemini_meta["capabilities"]["supports_vision"] == True
        assert gemini_meta["context_length"] == 1000000

    def test_filter_models_by_capability(self, mock_openrouter_models, cache_config):
        """Test filtering models by specific capabilities."""
        from src.openrouter_mcp.models.cache import ModelCache
        from src.openrouter_mcp.utils.metadata import batch_enhance_models
        
        cache = ModelCache(**cache_config)
        # Enhance models before adding to cache
        cache._memory_cache = batch_enhance_models(mock_openrouter_models["data"])
        
        # Filter vision-capable models
        vision_models = cache.filter_models(vision_capable=True)
        assert len(vision_models) == 1
        assert vision_models[0]["id"] == "google/gemini-2-5-pro"
        
        # Filter by provider
        openai_models = cache.filter_models(provider="OpenAI")
        assert len(openai_models) == 2
        assert all("openai" in model["id"] for model in openai_models)

    def test_get_latest_models(self, mock_openrouter_models, cache_config):
        """Test identifying latest/newest models."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        cache._memory_cache = mock_openrouter_models["data"]
        
        latest_models = cache.get_latest_models()
        
        # Should include models with version indicators
        latest_ids = [model["id"] for model in latest_models]
        assert "openai/gpt-5" in latest_ids
        assert "anthropic/claude-4" in latest_ids
        assert "deepseek/deepseek-v3" in latest_ids

    @pytest.mark.asyncio
    async def test_refresh_cache_force(self, mock_openrouter_models, cache_config):
        """Test force refreshing cache even when not expired."""
        from src.openrouter_mcp.models.cache import ModelCache
        
        cache = ModelCache(**cache_config)
        
        # Set valid cache
        cache._memory_cache = [{"id": "old/model", "name": "Old Model"}]
        cache._last_update = datetime.now()
        
        with patch('src.openrouter_mcp.client.openrouter.OpenRouterClient.from_env') as mock_client_getter:
            mock_client = MagicMock()
            mock_client_getter.return_value = mock_client
            
            async def mock_aenter(self):
                return mock_client
                
            async def mock_aexit(self, *args):
                return None
                
            mock_client.__aenter__ = mock_aenter
            mock_client.__aexit__ = mock_aexit
            async def mock_list_models():
                return mock_openrouter_models["data"]
            mock_client.list_models = mock_list_models
            
            with patch.object(cache, '_save_to_file_cache') as mock_save:
                await cache.refresh_cache(force=True)
                
                assert len(cache._memory_cache) == 5
                assert cache._memory_cache[0]["id"] == "openai/gpt-5"
                mock_save.assert_called_once()

    def test_cache_statistics(self, mock_openrouter_models, cache_config):
        """Test getting cache statistics."""
        from src.openrouter_mcp.models.cache import ModelCache
        from src.openrouter_mcp.utils.metadata import batch_enhance_models
        
        cache = ModelCache(**cache_config)
        # Enhance models before adding to cache
        cache._memory_cache = batch_enhance_models(mock_openrouter_models["data"])
        cache._last_update = datetime.now()
        
        stats = cache.get_cache_stats()
        
        assert stats["total_models"] == 5
        # Providers are lowercase after enhancement
        assert set(stats["providers"]) == {"openai", "anthropic", "google", "deepseek"}
        assert stats["vision_capable_count"] == 1
        assert "last_updated" in stats
        assert stats["cache_size_mb"] > 0


class TestModelCacheIntegration:
    """Integration tests for model cache with OpenRouter client."""

    @pytest.mark.asyncio
    async def test_openrouter_client_with_cache(self):
        """Test OpenRouter client integrated with model cache."""
        # This test will be implemented after cache system is built
        pass

    @pytest.mark.asyncio
    async def test_mcp_handlers_use_cached_models(self):
        """Test that MCP handlers use cached model information."""
        # This test will be implemented after cache integration
        pass

    def test_cache_persistence_across_restarts(self):
        """Test that cache persists across application restarts."""
        # This test will be implemented with file cache system
        pass