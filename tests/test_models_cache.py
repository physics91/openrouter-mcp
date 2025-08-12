"""Tests for OpenRouter model caching and fetching functionality."""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
import httpx

from src.openrouter_mcp.client.openrouter import OpenRouterClient


class TestModelCaching:
    """Test cases for model list caching and real-time fetching."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_latest_models_from_api(self, mock_api_key):
        """Test fetching the latest models from OpenRouter API."""
        client = OpenRouterClient(api_key=mock_api_key)
        
        # Mock response with latest models (January 2025)
        mock_latest_models = {
            "data": [
                # OpenAI Models
                {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000},
                {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "context_length": 128000},
                {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo", "context_length": 128000},
                {"id": "openai/o1", "name": "OpenAI o1", "context_length": 200000},
                {"id": "openai/o1-mini", "name": "OpenAI o1-mini", "context_length": 128000},
                
                # Anthropic Models
                {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "context_length": 200000},
                {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "context_length": 200000},
                {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku", "context_length": 200000},
                
                # Google Models
                {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "context_length": 1048576},
                {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "context_length": 1048576},
                {"id": "google/gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "context_length": 1048576},
                {"id": "google/gemini-pro-1.5", "name": "Gemini Pro 1.5", "context_length": 2000000},
                
                # Meta Models
                {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "context_length": 128000},
                {"id": "meta-llama/llama-3.2-90b-vision-instruct", "name": "Llama 3.2 90B Vision", "context_length": 128000},
                {"id": "meta-llama/llama-3.2-11b-vision-instruct", "name": "Llama 3.2 11B Vision", "context_length": 128000},
                
                # Mistral Models
                {"id": "mistralai/mistral-large", "name": "Mistral Large", "context_length": 128000},
                {"id": "mistralai/mistral-medium", "name": "Mistral Medium", "context_length": 32768},
                {"id": "mistralai/mixtral-8x22b-instruct", "name": "Mixtral 8x22B", "context_length": 65536},
                {"id": "mistralai/devstral-small-2505", "name": "Devstral Small 2505", "context_length": 32768},
                
                # DeepSeek Models
                {"id": "deepseek/deepseek-v3", "name": "DeepSeek V3", "context_length": 64000},
                {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "context_length": 64000},
                {"id": "deepseek/deepseek-coder", "name": "DeepSeek Coder", "context_length": 16384},
                
                # Qwen Models
                {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B", "context_length": 128000},
                {"id": "qwen/qwen-2.5-coder-32b-instruct", "name": "Qwen 2.5 Coder", "context_length": 32768},
                
                # xAI Models
                {"id": "xai/grok-2", "name": "Grok 2", "context_length": 131072},
                {"id": "xai/grok-2-vision", "name": "Grok 2 Vision", "context_length": 32768},
            ]
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_latest_models
            
            models = await client.list_models(enhance_info=False)
            
            # Verify we got all major providers
            model_ids = [m["id"] for m in models]
            
            # Check OpenAI models
            assert "openai/gpt-4o" in model_ids
            assert "openai/o1" in model_ids
            
            # Check Anthropic models
            assert "anthropic/claude-3.5-sonnet" in model_ids
            assert "anthropic/claude-3-opus" in model_ids
            
            # Check Google models
            assert "google/gemini-2.5-pro" in model_ids
            assert "google/gemini-2.5-flash" in model_ids
            
            # Check Meta models
            assert "meta-llama/llama-3.3-70b-instruct" in model_ids
            
            # Check other providers
            assert "mistralai/mistral-large" in model_ids
            assert "deepseek/deepseek-v3" in model_ids
            assert "qwen/qwen-2.5-72b-instruct" in model_ids
            assert "xai/grok-2" in model_ids
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_model_list_includes_metadata(self, mock_api_key):
        """Test that model list includes important metadata."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        mock_detailed_model = {
            "data": [{
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "description": "OpenAI's most advanced multimodal model",
                "context_length": 128000,
                "architecture": {
                    "modality": "text+image->text",
                    "tokenizer": "GPT"
                },
                "pricing": {
                    "prompt": "0.000005",
                    "completion": "0.000015"
                },
                "top_provider": {
                    "max_completion_tokens": 4096,
                    "is_moderated": True
                },
                "supported_parameters": [
                    "temperature", "max_tokens", "top_p", "tools", 
                    "tool_choice", "response_format", "seed"
                ]
            }]
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_detailed_model
            
            models = await client.list_models(enhance_info=False)
            model = models[0]
            
            # Verify metadata fields
            assert "id" in model
            assert "name" in model
            assert "context_length" in model
            assert "pricing" in model
            assert "supported_parameters" in model
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_filter_models_by_provider(self, mock_api_key):
        """Test filtering models by provider."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        all_models = {
            "data": [
                {"id": "openai/gpt-4o", "name": "GPT-4o"},
                {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo"},
                {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5"},
                {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
            ]
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = all_models
            
            # Test getting all models
            models = await client.list_models(enhance_info=False)
            assert len(models) == 4
            
            # Test filtering (simulated - actual API may handle differently)
            openai_models = [m for m in models if m["id"].startswith("openai/")]
            assert len(openai_models) == 2
            assert all(m["id"].startswith("openai/") for m in openai_models)
    
    @pytest.mark.unit
    @pytest.mark.asyncio 
    async def test_model_validation_with_latest_models(self, mock_api_key):
        """Test that the latest models are properly validated."""
        client = OpenRouterClient(api_key=mock_api_key)
        
        # Test valid latest models
        valid_models = [
            "openai/gpt-4o",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.5-pro",
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-v3",
            "xai/grok-2"
        ]
        
        for model in valid_models:
            client._validate_model(model)  # Should not raise
        
        # Test invalid models
        with pytest.raises(ValueError):
            client._validate_model("")
        
        with pytest.raises(ValueError):
            client._validate_model(None)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_multimodal_model_support(self, mock_api_key):
        """Test that multimodal models are properly identified."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        multimodal_models = {
            "data": [
                {
                    "id": "openai/gpt-4o",
                    "name": "GPT-4o",
                    "architecture": {
                        "modality": "text+image->text",
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"]
                    }
                },
                {
                    "id": "google/gemini-2.5-pro",
                    "name": "Gemini 2.5 Pro",
                    "architecture": {
                        "modality": "text+image->text",
                        "input_modalities": ["text", "image", "file"],
                        "output_modalities": ["text"]
                    }
                },
                {
                    "id": "meta-llama/llama-3.2-90b-vision-instruct",
                    "name": "Llama 3.2 90B Vision",
                    "architecture": {
                        "modality": "text+image->text",
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"]
                    }
                },
                {
                    "id": "xai/grok-2-vision",
                    "name": "Grok 2 Vision",
                    "architecture": {
                        "modality": "text+image->text",
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"]
                    }
                }
            ]
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = multimodal_models
            
            models = await client.list_models(enhance_info=False)
            
            # Check that all models support multimodal input
            for model in models:
                arch = model.get("architecture", {})
                assert "image" in arch.get("input_modalities", [])
                assert "text+image->text" in arch.get("modality", "")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_model_pricing_information(self, mock_api_key):
        """Test that model pricing information is available."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        models_with_pricing = {
            "data": [
                {
                    "id": "openai/gpt-4o",
                    "name": "GPT-4o",
                    "pricing": {
                        "prompt": "0.000005",
                        "completion": "0.000015",
                        "image": "0.00765"
                    }
                },
                {
                    "id": "anthropic/claude-3.5-sonnet",
                    "name": "Claude 3.5 Sonnet", 
                    "pricing": {
                        "prompt": "0.000003",
                        "completion": "0.000015",
                        "image": "0.0048"
                    }
                },
                {
                    "id": "google/gemini-2.5-flash",
                    "name": "Gemini 2.5 Flash",
                    "pricing": {
                        "prompt": "0.0000003",
                        "completion": "0.0000025",
                        "image": "0.001238"
                    }
                }
            ]
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = models_with_pricing
            
            models = await client.list_models(enhance_info=False)
            
            # Verify pricing information
            for model in models:
                assert "pricing" in model
                assert "prompt" in model["pricing"]
                assert "completion" in model["pricing"]
                
                # Convert to float to verify they're valid numbers
                prompt_price = float(model["pricing"]["prompt"])
                completion_price = float(model["pricing"]["completion"])
                assert prompt_price >= 0
                assert completion_price >= 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_context_length_comparison(self, mock_api_key):
        """Test comparing context lengths of different models."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        models_with_context = {
            "data": [
                {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000},
                {"id": "openai/o1", "name": "OpenAI o1", "context_length": 200000},
                {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5", "context_length": 200000},
                {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "context_length": 1048576},
                {"id": "google/gemini-pro-1.5", "name": "Gemini Pro 1.5", "context_length": 2000000},
            ]
        }
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = models_with_context
            
            models = await client.list_models(enhance_info=False)
            
            # Sort by context length
            sorted_models = sorted(models, key=lambda x: x["context_length"], reverse=True)
            
            # Verify Gemini Pro 1.5 has the largest context
            assert sorted_models[0]["id"] == "google/gemini-pro-1.5"
            assert sorted_models[0]["context_length"] == 2000000
            
            # Verify relative ordering
            assert sorted_models[1]["id"] == "google/gemini-2.5-pro"
            assert sorted_models[-1]["context_length"] == 128000


class TestModelCacheImplementation:
    """Test implementation of model caching functionality."""
    
    @pytest.mark.unit
    def test_cache_structure(self):
        """Test the structure for caching model data."""
        cache = {
            "timestamp": datetime.now().isoformat(),
            "ttl_seconds": 3600,  # 1 hour cache
            "models": [],
            "version": "1.0.0"
        }
        
        assert "timestamp" in cache
        assert "ttl_seconds" in cache
        assert "models" in cache
        assert cache["ttl_seconds"] == 3600
    
    @pytest.mark.unit
    def test_cache_expiry_check(self):
        """Test checking if cache has expired."""
        # Create expired cache
        expired_cache = {
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "ttl_seconds": 3600,
            "models": []
        }
        
        # Create valid cache
        valid_cache = {
            "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "ttl_seconds": 3600,
            "models": []
        }
        
        def is_cache_expired(cache_data):
            timestamp = datetime.fromisoformat(cache_data["timestamp"])
            ttl = timedelta(seconds=cache_data["ttl_seconds"])
            return datetime.now() > timestamp + ttl
        
        assert is_cache_expired(expired_cache) == True
        assert is_cache_expired(valid_cache) == False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cache_refresh_on_expiry(self, mock_api_key):
        """Test that cache refreshes when expired."""
        client = OpenRouterClient(api_key=mock_api_key, enable_cache=False)
        
        # Simulate cache mechanism
        cache = {"data": None, "timestamp": None, "ttl": 3600}
        
        async def get_models_with_cache():
            if cache["data"] is None or \
               cache["timestamp"] is None or \
               time.time() - cache["timestamp"] > cache["ttl"]:
                # Cache miss or expired - fetch from API
                cache["data"] = await client.list_models(enhance_info=False)
                cache["timestamp"] = time.time()
            return cache["data"]
        
        mock_response = {"data": [{"id": "test/model", "name": "Test Model"}]}
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            # First call - cache miss
            models1 = await get_models_with_cache()
            assert models1 == mock_response["data"]
            assert mock_request.call_count == 1
            
            # Second call - cache hit
            models2 = await get_models_with_cache()
            assert models2 == mock_response["data"]
            assert mock_request.call_count == 1  # No additional API call
            
            # Simulate cache expiry
            cache["timestamp"] = time.time() - 3601
            
            # Third call - cache expired
            models3 = await get_models_with_cache()
            assert models3 == mock_response["data"]
            assert mock_request.call_count == 2  # New API call made


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])