"""Model caching functionality for OpenRouter MCP Server."""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelCache:
    """Manages caching of OpenRouter model information."""
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_seconds: int = 3600,
        enable_file_cache: bool = True
    ):
        """Initialize the model cache.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to system temp.
            ttl_seconds: Time-to-live for cache in seconds. Default 1 hour.
            enable_file_cache: Whether to enable file-based caching.
        """
        self.ttl_seconds = ttl_seconds
        self.enable_file_cache = enable_file_cache
        self._memory_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[float] = None
        
        if enable_file_cache:
            if cache_dir is None:
                # Use system temp directory
                import tempfile
                self.cache_dir = Path(tempfile.gettempdir()) / "openrouter_mcp_cache"
            else:
                self.cache_dir = Path(cache_dir)
            
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file = self.cache_dir / "models_cache.json"
            logger.info(f"Model cache initialized at: {self.cache_file}")
        else:
            self.cache_dir = None
            self.cache_file = None
            logger.info("Model cache initialized (memory only)")
    
    def is_expired(self, timestamp: float) -> bool:
        """Check if cache has expired based on timestamp.
        
        Args:
            timestamp: Unix timestamp of cache creation.
            
        Returns:
            True if cache is expired, False otherwise.
        """
        return time.time() - timestamp > self.ttl_seconds
    
    def get(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached models if available and not expired.
        
        Returns:
            List of model dictionaries or None if cache miss/expired.
        """
        # Check memory cache first
        if self._memory_cache and self._cache_timestamp:
            if not self.is_expired(self._cache_timestamp):
                logger.debug("Model cache hit (memory)")
                return self._memory_cache.get("models", [])
        
        # Check file cache if enabled
        if self.enable_file_cache and self.cache_file and self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                timestamp = cache_data.get("timestamp", 0)
                if not self.is_expired(timestamp):
                    models = cache_data.get("models", [])
                    # Update memory cache
                    self._memory_cache = cache_data
                    self._cache_timestamp = timestamp
                    logger.debug("Model cache hit (file)")
                    return models
                else:
                    logger.debug("Model cache expired (file)")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read cache file: {e}")
        
        logger.debug("Model cache miss")
        return None
    
    def set(self, models: List[Dict[str, Any]]) -> None:
        """Save models to cache.
        
        Args:
            models: List of model dictionaries to cache.
        """
        timestamp = time.time()
        cache_data = {
            "timestamp": timestamp,
            "ttl_seconds": self.ttl_seconds,
            "models": models,
            "version": "1.0.0",
            "cached_at": datetime.now().isoformat()
        }
        
        # Update memory cache
        self._memory_cache = cache_data
        self._cache_timestamp = timestamp
        
        # Save to file if enabled
        if self.enable_file_cache and self.cache_file:
            try:
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2)
                logger.debug(f"Model cache saved to {self.cache_file}")
            except IOError as e:
                logger.warning(f"Failed to write cache file: {e}")
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._memory_cache = None
        self._cache_timestamp = None
        
        if self.enable_file_cache and self.cache_file and self.cache_file.exists():
            try:
                self.cache_file.unlink()
                logger.debug("Model cache file deleted")
            except IOError as e:
                logger.warning(f"Failed to delete cache file: {e}")
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about the current cache state.
        
        Returns:
            Dictionary with cache information.
        """
        info = {
            "enabled": True,
            "file_cache_enabled": self.enable_file_cache,
            "ttl_seconds": self.ttl_seconds,
            "memory_cache_exists": self._memory_cache is not None,
            "file_cache_exists": False,
            "is_expired": True,
            "cached_at": None,
            "expires_at": None,
            "model_count": 0
        }
        
        if self._memory_cache and self._cache_timestamp:
            info["is_expired"] = self.is_expired(self._cache_timestamp)
            info["cached_at"] = datetime.fromtimestamp(self._cache_timestamp).isoformat()
            info["expires_at"] = datetime.fromtimestamp(
                self._cache_timestamp + self.ttl_seconds
            ).isoformat()
            info["model_count"] = len(self._memory_cache.get("models", []))
        
        if self.enable_file_cache and self.cache_file:
            info["cache_file"] = str(self.cache_file)
            info["file_cache_exists"] = self.cache_file.exists()
        
        return info


class EnhancedModelInfo:
    """Enhanced model information with categorization and metadata."""
    
    # Latest models as of January 2025
    LATEST_MODELS = {
        "openai": [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-4-turbo",
            "openai/gpt-4-turbo-preview",
            "openai/o1",
            "openai/o1-mini",
            "openai/o1-preview",
        ],
        "anthropic": [
            "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3-opus",
            "anthropic/claude-3-haiku",
            "anthropic/claude-3-sonnet",
        ],
        "google": [
            "google/gemini-2.5-pro",
            "google/gemini-2.5-pro-preview",
            "google/gemini-2.5-flash",
            "google/gemini-2.5-flash-lite",
            "google/gemini-pro-1.5",
            "google/gemini-pro",
            "google/gemini-pro-vision",
        ],
        "meta": [
            "meta-llama/llama-3.3-70b-instruct",
            "meta-llama/llama-3.2-90b-vision-instruct",
            "meta-llama/llama-3.2-11b-vision-instruct",
            "meta-llama/llama-3.2-3b-instruct",
            "meta-llama/llama-3.2-1b-instruct",
            "meta-llama/llama-3.1-405b-instruct",
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
        ],
        "mistral": [
            "mistralai/mistral-large",
            "mistralai/mistral-medium",
            "mistralai/mixtral-8x22b-instruct",
            "mistralai/mixtral-8x7b-instruct",
            "mistralai/mistral-7b-instruct",
            "mistralai/devstral-small-2505",
            "mistralai/codestral-latest",
        ],
        "deepseek": [
            "deepseek/deepseek-v3",
            "deepseek/deepseek-chat",
            "deepseek/deepseek-coder",
            "deepseek/deepseek-v2.5",
        ],
        "qwen": [
            "qwen/qwen-2.5-72b-instruct",
            "qwen/qwen-2.5-32b-instruct",
            "qwen/qwen-2.5-14b-instruct",
            "qwen/qwen-2.5-7b-instruct",
            "qwen/qwen-2.5-coder-32b-instruct",
            "qwen/qwen-2-vl-72b-instruct",
        ],
        "xai": [
            "xai/grok-2",
            "xai/grok-2-vision",
            "xai/grok-beta",
        ],
        "cohere": [
            "cohere/command-r-plus",
            "cohere/command-r",
            "cohere/command",
        ],
        "perplexity": [
            "perplexity/llama-3.1-sonar-large-128k-online",
            "perplexity/llama-3.1-sonar-small-128k-online",
            "perplexity/llama-3.1-sonar-huge-128k-online",
        ]
    }
    
    # Model categories
    CATEGORIES = {
        "multimodal": [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "google/gemini-2.5-pro",
            "google/gemini-2.5-flash",
            "google/gemini-pro-vision",
            "meta-llama/llama-3.2-90b-vision-instruct",
            "meta-llama/llama-3.2-11b-vision-instruct",
            "xai/grok-2-vision",
        ],
        "coding": [
            "deepseek/deepseek-coder",
            "qwen/qwen-2.5-coder-32b-instruct",
            "mistralai/codestral-latest",
            "mistralai/devstral-small-2505",
        ],
        "reasoning": [
            "openai/o1",
            "openai/o1-mini",
            "openai/o1-preview",
            "google/gemini-2.5-pro",
            "deepseek/deepseek-v3",
        ],
        "online": [
            "perplexity/llama-3.1-sonar-large-128k-online",
            "perplexity/llama-3.1-sonar-small-128k-online",
            "perplexity/llama-3.1-sonar-huge-128k-online",
        ],
        "large_context": [
            "google/gemini-2.5-pro",  # 1M+ context
            "google/gemini-2.5-flash",  # 1M+ context
            "google/gemini-pro-1.5",  # 2M context
            "anthropic/claude-3.5-sonnet",  # 200K context
            "anthropic/claude-3-opus",  # 200K context
            "openai/o1",  # 200K context
        ]
    }
    
    @classmethod
    def get_provider(cls, model_id: str) -> Optional[str]:
        """Extract provider from model ID.
        
        Args:
            model_id: Model identifier (e.g., "openai/gpt-4o")
            
        Returns:
            Provider name or None if not found.
        """
        if "/" in model_id:
            return model_id.split("/")[0]
        return None
    
    @classmethod
    def is_latest_model(cls, model_id: str) -> bool:
        """Check if a model is in the latest models list.
        
        Args:
            model_id: Model identifier to check.
            
        Returns:
            True if model is in latest list, False otherwise.
        """
        for provider_models in cls.LATEST_MODELS.values():
            if model_id in provider_models:
                return True
        return False
    
    @classmethod
    def get_categories(cls, model_id: str) -> List[str]:
        """Get categories for a model.
        
        Args:
            model_id: Model identifier.
            
        Returns:
            List of category names the model belongs to.
        """
        categories = []
        for category, models in cls.CATEGORIES.items():
            if model_id in models:
                categories.append(category)
        return categories
    
    @classmethod
    def enhance_model_info(cls, model: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance model information with additional metadata.
        
        Args:
            model: Original model dictionary from API.
            
        Returns:
            Enhanced model dictionary with additional fields.
        """
        enhanced = model.copy()
        model_id = model.get("id", "")
        
        # Add provider info
        enhanced["provider"] = cls.get_provider(model_id)
        
        # Add latest flag
        enhanced["is_latest"] = cls.is_latest_model(model_id)
        
        # Add categories
        enhanced["categories"] = cls.get_categories(model_id)
        
        # Add multimodal flag for convenience
        enhanced["is_multimodal"] = "multimodal" in enhanced["categories"]
        
        # Add large context flag (>100K tokens)
        context_length = model.get("context_length", 0)
        enhanced["is_large_context"] = context_length > 100000
        
        return enhanced