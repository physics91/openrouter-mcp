#!/usr/bin/env python3
"""
Dynamic model caching system for OpenRouter MCP Server.

This module provides intelligent caching of AI model information from OpenRouter API,
including memory and file-based caching with TTL support.
"""

import asyncio
import json
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
import re
import portalocker

# Import metadata utilities
from ..utils.metadata import (
    enhance_model_metadata,
    batch_enhance_models,
    ModelCategory,
    ModelProvider,
    extract_provider_from_id,
    determine_model_category
)
from ..utils.http import build_openrouter_headers
from ..utils.env import get_env_value
from ..config.constants import APIConfig, CacheConfig, EnvVars

# Import client locally to avoid circular imports


logger = logging.getLogger(__name__)


class HTTPTransport:
    """
    Shared HTTP transport layer for making API requests.

    This class encapsulates HTTP client logic and can be reused across
    different components to avoid code duplication.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = APIConfig.BASE_URL,
        timeout: float = APIConfig.DEFAULT_TIMEOUT
    ):
        """
        Initialize HTTP transport.

        Args:
            api_key: OpenRouter API key
            base_url: Base URL for API
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[Any] = None

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        return build_openrouter_headers(self.api_key, fallback_to_env=True)

    async def get(self, endpoint: str) -> Dict[str, Any]:
        """
        Make GET request to API.

        Args:
            endpoint: API endpoint path

        Returns:
            Response data as dictionary
        """
        import httpx

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    def close(self):
        """Close transport (for compatibility)."""
        pass


class ModelCache:
    """
    Intelligent caching system for OpenRouter AI models.
    
    Features:
    - Memory cache with configurable TTL
    - File-based persistence across restarts  
    - Smart model metadata extraction
    - Provider and capability filtering
    - Latest model identification
    """
    
    def __init__(
        self,
        ttl_hours: float = CacheConfig.DEFAULT_TTL_HOURS,
        max_memory_items: int = 1000,
        cache_file: str = CacheConfig.MODEL_CACHE_FILE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize model cache.

        Args:
            ttl_hours: Time-to-live for cache in hours (supports fractional values, e.g., 0.0833 for 5 minutes)
            max_memory_items: Maximum items to keep in memory
            cache_file: Path to cache file for persistence
            api_key: Optional API key for fetching models (falls back to env var)
            base_url: Optional base URL for API (falls back to env var)
        """
        self.ttl_seconds = int(ttl_hours * 3600)
        self.max_memory_items = max_memory_items
        self.cache_file = cache_file

        # Store credentials for API calls (with fallback to environment)
        self._api_key = api_key
        self._base_url = base_url

        # Internal cache storage with thread-safe access
        self._memory_cache: List[Dict[str, Any]] = []
        self._last_update: Optional[datetime] = None
        self._cache_lock = threading.RLock()  # Reentrant lock for thread safety

        # Thread pool executor for blocking I/O operations
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cache-io")

        # Lazy initialization of HTTP transport (created on first API call)
        self._transport: Optional[HTTPTransport] = None
        self._transport_initialized = False

        # Load existing cache on initialization
        self._load_cache_on_startup()

        logger.info(f"ModelCache initialized with {ttl_hours}h TTL, file: {cache_file}")
    
    def _load_cache_on_startup(self) -> None:
        """Load cache from file during initialization (synchronous)."""
        try:
            models, last_update = self._load_from_file_cache_sync()
            if models:
                with self._cache_lock:
                    self._memory_cache = models
                    self._last_update = last_update
                logger.info(f"Loaded {len(models)} models from cache file")
        except Exception as e:
            logger.warning(f"Failed to load cache on startup: {e}")
    
    def _ensure_transport(self) -> None:
        """
        Ensure HTTP transport is initialized.

        This is called lazily on first API request to allow environment
        variables to be set after cache initialization (useful for testing).
        """
        if self._transport_initialized:
            return

        api_key = self._api_key or get_env_value(EnvVars.API_KEY)
        base_url = self._base_url or get_env_value(EnvVars.BASE_URL, APIConfig.BASE_URL)

        if api_key:
            self._transport = HTTPTransport(api_key=api_key, base_url=base_url)
        else:
            self._transport = None
            logger.warning("ModelCache initialized without API key - API fetching will be unavailable")

        self._transport_initialized = True

    def is_expired(self) -> bool:
        """Check if cache is expired based on TTL."""
        if self._last_update is None:
            return True

        expiry_time = self._last_update + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry_time
    
    async def _fetch_models_from_api(self) -> List[Dict[str, Any]]:
        """
        Fetch latest models from OpenRouter API and enhance with metadata.

        Uses shared HTTPTransport to avoid code duplication and maintains
        the async-first design pattern.
        """
        try:
            # Ensure transport is initialized (lazy initialization)
            self._ensure_transport()

            if not self._transport:
                raise ValueError(
                    "API key is required. Provide via api_key parameter or "
                    f"{EnvVars.API_KEY} environment variable"
                )

            # Use shared transport layer
            data = await self._transport.get("/models")
            raw_models = data.get("data", [])

            logger.info(f"Fetched {len(raw_models)} models from OpenRouter API (raw)")

            # Enhance models with metadata in thread executor (CPU-bound)
            loop = asyncio.get_event_loop()
            enhanced_models = await loop.run_in_executor(
                self._executor,
                batch_enhance_models,
                raw_models
            )
            logger.info(f"Enhanced {len(enhanced_models)} models with metadata")

            return enhanced_models

        except Exception as e:
            logger.error(f"Failed to fetch models from API: {e}")
            raise

    @staticmethod
    def _lock_timeout(default_seconds: int) -> Optional[int]:
        """Return None on Windows to avoid portalocker timeout warnings."""
        return None if sys.platform.startswith("win") else default_seconds

    def _save_to_file_cache_sync(self, models: List[Dict[str, Any]]) -> None:
        """
        Synchronous file save operation (runs in thread executor).

        Save models to file cache with file locking to prevent concurrent write corruption.
        Uses portalocker to acquire an exclusive lock before writing, ensuring that
        multiple processes/threads don't corrupt the cache file.

        Args:
            models: List of model dictionaries to cache

        Raises:
            portalocker.LockException: If unable to acquire lock within timeout
        """
        try:
            cache_data = {
                "models": models,
                "updated_at": datetime.now().isoformat()
            }

            cache_path = Path(self.cache_file)
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Use file locking to prevent concurrent write corruption
            # LOCK_EX = exclusive lock, timeout=5 seconds
            with portalocker.Lock(
                cache_path,
                mode='w',
                encoding='utf-8',
                timeout=self._lock_timeout(5),
                flags=portalocker.LOCK_EX
            ) as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                # Ensure data is written to disk
                f.flush()

            logger.debug(f"Saved {len(models)} models to cache file: {self.cache_file} (with file lock)")

        except portalocker.LockException as e:
            logger.error(f"Failed to acquire file lock for cache write: {e}")
            logger.warning("Cache write skipped due to lock timeout - another process may be writing")
        except Exception as e:
            logger.error(f"Failed to save models to file cache: {e}")

    def _save_to_file_cache(self, models: List[Dict[str, Any]]) -> None:
        """
        Synchronous wrapper for file save operation.

        This is kept synchronous for compatibility with tests and callers that
        invoke the method directly without awaiting.
        """
        self._save_to_file_cache_sync(models)
    
    def _load_from_file_cache_sync(self) -> Tuple[List[Dict[str, Any]], Optional[datetime]]:
        """
        Synchronous file load operation (runs in thread executor).

        Load models from file cache with shared lock to prevent reading during writes.
        Uses portalocker to acquire a shared lock before reading, ensuring data
        consistency when multiple processes are accessing the cache.

        Returns:
            Tuple of (models list, last update datetime)
        """
        cache_path = Path(self.cache_file)

        if not cache_path.exists():
            return [], None

        try:
            # Use shared lock (LOCK_SH) for reading - allows concurrent reads   
            # but blocks if someone has an exclusive write lock
            with portalocker.Lock(
                self.cache_file,
                mode='r',
                encoding='utf-8',
                timeout=self._lock_timeout(3),
                flags=portalocker.LOCK_SH
            ) as f:
                cache_data = json.load(f)

            models = cache_data.get("models", [])
            updated_at_str = cache_data.get("updated_at")

            updated_at = None
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str)

            logger.debug(f"Loaded {len(models)} models from cache file (with shared lock)")
            return models, updated_at

        except portalocker.LockException as e:
            logger.warning(f"Failed to acquire shared lock for cache read: {e}")
            logger.warning("Cache read failed - file may be locked for writing")
            return [], None
        except Exception as e:
            logger.error(f"Failed to load models from file cache: {e}")
            return [], None

    def _load_from_file_cache(self) -> Tuple[List[Dict[str, Any]], Optional[datetime]]:
        """
        Synchronous wrapper for file load operation.

        This is kept synchronous for compatibility with tests and callers that
        invoke the method directly without awaiting.
        """
        return self._load_from_file_cache_sync()
    
    def iter_models(self) -> Iterator[Dict[str, Any]]:
        """
        Iterate over cached models without copying.

        Returns:
            Iterator over model dictionaries

        Note:
            This is thread-safe for reading, but the cache should not be
            modified during iteration.
        """
        with self._cache_lock:
            # Return iterator over a shallow copy to prevent modification
            # but avoid deep copying all model data
            for model in self._memory_cache:
                yield model

    def get_models_slice(self, start: int = 0, end: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get a slice of cached models without copying the entire cache.

        Args:
            start: Start index (inclusive)
            end: End index (exclusive), None for end of list

        Returns:
            List slice of model dictionaries
        """
        with self._cache_lock:
            return self._memory_cache[start:end]

    def get_models_count(self) -> int:
        """
        Get the number of cached models.

        Returns:
            Count of cached models
        """
        with self._cache_lock:
            return len(self._memory_cache)

    async def get_models(self, force_refresh: bool = False, copy: bool = True) -> List[Dict[str, Any]]:
        """
        Get models with intelligent caching.

        Args:
            force_refresh: Force refresh from API even if cache is valid
            copy: If True, return a copy of the cache; if False, return direct reference
                  (WARNING: Setting copy=False requires the caller to not modify the list)

        Returns:
            List of model dictionaries
        """
        # Return cached models if valid and not forcing refresh
        if not force_refresh and not self.is_expired():
            with self._cache_lock:
                if self._memory_cache:
                    logger.debug("Returning cached models (cache hit)")
                    # Return copy or reference based on parameter
                    return list(self._memory_cache) if copy else self._memory_cache

        # Cache miss - fetch from API
        try:
            models = await self._fetch_models_from_api()

            # Update cache with thread safety
            with self._cache_lock:
                self._memory_cache = models
                self._last_update = datetime.now()

            # Persist to file without blocking the event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._save_to_file_cache, models)

            logger.info(f"Cache updated with {len(models)} models")
            return models

        except Exception as e:
            # Fallback to file cache if API fails
            logger.warning(f"API fetch failed, trying file cache: {e}")
            loop = asyncio.get_running_loop()
            models, _ = await loop.run_in_executor(self._executor, self._load_from_file_cache)

            if models:
                logger.info(f"Using {len(models)} models from file cache fallback")
                return models
            else:
                logger.error("No cached models available and API failed")
                return []
    
    async def refresh_cache(self, force: bool = False) -> None:
        """
        Explicitly refresh the cache.
        
        Args:
            force: Force refresh even if cache is not expired
        """
        if force or self.is_expired():
            await self.get_models(force_refresh=True)
            logger.info("Cache manually refreshed")
        else:
            logger.debug("Cache refresh skipped - not expired")
    
    def get_model_metadata(self, model_id: str) -> Dict[str, Any]:
        """
        Get enhanced metadata for a specific model.

        Args:
            model_id: Model identifier (e.g., 'openai/gpt-5')

        Returns:
            Dictionary with enhanced model metadata
        """
        # Find model in cache with thread safety
        with self._cache_lock:
            if isinstance(self._memory_cache, list):
                for m in self._memory_cache:
                    if m.get("id") == model_id:
                        # Return the already enhanced metadata
                        # (models are enhanced when fetched from API)
                        return m

        return {"error": f"Model {model_id} not found in cache"}
    
    def filter_models_by_metadata(
        self,
        provider: Optional[Union[str, ModelProvider]] = None,
        category: Optional[Union[str, ModelCategory]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        performance_tier: Optional[str] = None,
        cost_tier: Optional[str] = None,
        min_quality_score: Optional[float] = None,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter models by enhanced metadata attributes.

        Args:
            provider: Filter by provider
            category: Filter by category
            capabilities: Filter by specific capabilities
            performance_tier: Filter by performance tier
            cost_tier: Filter by cost tier
            min_quality_score: Minimum quality score
            tags: Filter by tags

        Returns:
            Filtered list of models
        """
        with self._cache_lock:
            if not isinstance(self._memory_cache, list):
                return []

            filtered = []

            for model in self._memory_cache:
                # Provider filter
                if provider is not None:
                    model_provider = model.get("provider", "unknown")
                    # Normalize both values to strings for comparison
                    provider_str = provider.value if hasattr(provider, 'value') else str(provider).lower()
                    model_provider_str = model_provider.value if hasattr(model_provider, 'value') else str(model_provider).lower()

                    if model_provider_str != provider_str:
                        continue

                # Category filter
                if category is not None:
                    model_category = model.get("category", "unknown")
                    # Normalize both values to strings for comparison
                    category_str = category.value if hasattr(category, 'value') else str(category).lower()
                    model_category_str = model_category.value if hasattr(model_category, 'value') else str(model_category).lower()

                    if model_category_str != category_str:
                        continue

                # Capabilities filter
                if capabilities:
                    model_caps = model.get("capabilities", {})
                    match = True
                    for key, value in capabilities.items():
                        if key == "min_context_length":
                            if model_caps.get("max_tokens", 0) < value:
                                match = False
                                break
                        elif model_caps.get(key) != value:
                            match = False
                            break
                    if not match:
                        continue

                # Performance tier filter
                if performance_tier and model.get("performance_tier") != performance_tier:
                    continue

                # Cost tier filter
                if cost_tier and model.get("cost_tier") != cost_tier:
                    continue

                # Quality score filter
                if min_quality_score is not None:
                    if model.get("quality_score", 0) < min_quality_score:
                        continue

                # Tags filter
                if tags:
                    model_tags = set(model.get("tags", []))
                    if not any(tag in model_tags for tag in tags):
                        continue

                filtered.append(model)

            return filtered
    
    def get_models_by_performance_tier(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get models grouped by performance tier.

        Returns:
            Dictionary with tiers as keys and model lists as values
        """
        with self._cache_lock:
            if not isinstance(self._memory_cache, list):
                return {}

            tiers = {"premium": [], "standard": [], "economy": []}

            for model in self._memory_cache:
                tier = model.get("performance_tier", "standard")
                if tier in tiers:
                    tiers[tier].append(model)

            return tiers
    
    def filter_models(
        self,
        provider: Optional[str] = None,
        vision_capable: Optional[bool] = None,
        reasoning_model: Optional[bool] = None,
        long_context: Optional[bool] = None,
        free_only: Optional[bool] = None,
        min_context: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter models by capabilities and attributes.

        Args:
            provider: Filter by provider name
            vision_capable: Filter vision-capable models
            reasoning_model: Filter reasoning models
            long_context: Filter long context models (>100k tokens)
            free_only: Filter free models only
            min_context: Minimum context length

        Returns:
            Filtered list of models
        """
        with self._cache_lock:
            if not isinstance(self._memory_cache, list):
                return []

            filtered = []

            for model in self._memory_cache:
                model_id = model.get("id", "")
                metadata = self.get_model_metadata(model_id)

                # Apply filters
                if provider and metadata.get("provider", "").lower() != provider.lower():
                    continue

                if vision_capable is not None:
                    caps = metadata.get("capabilities", {})
                    if caps.get("supports_vision", False) != vision_capable:
                        continue

                if reasoning_model is not None:
                    # Check if model is a reasoning model based on id or description
                    is_reasoning = "o1" in model_id or "reasoning" in metadata.get("description", "").lower()
                    if is_reasoning != reasoning_model:
                        continue

                if long_context is not None:
                    # Long context = > 100k tokens
                    is_long = metadata.get("context_length", 0) > 100000
                    if is_long != long_context:
                        continue

                if free_only is not None:
                    # Check if model is free based on cost_tier
                    is_free = metadata.get("cost_tier") == "free"
                    if is_free != free_only:
                        continue

                if min_context is not None and metadata.get("context_length", 0) < min_context:
                    continue

                filtered.append(model)

            return filtered
    
    def get_latest_models(self) -> List[Dict[str, Any]]:
        """
        Get the latest/newest models based on version identifiers.

        Returns:
            List of latest model versions
        """
        with self._cache_lock:
            if not isinstance(self._memory_cache, list):
                return []

            # Patterns that indicate latest models
            latest_patterns = [
                r"gpt-5",      # GPT-5
                r"claude-4",   # Claude 4
                r"gemini-2\.5", # Gemini 2.5
                r"deepseek-v3", # DeepSeek V3
                r"o1",         # OpenAI o1 series
                r"grok-3",     # Grok 3
                r"llama.*4",   # Llama 4 series
            ]

            latest_models = []

            for model in self._memory_cache:
                model_id = model.get("id", "").lower()

                # Check if model matches latest patterns
                for pattern in latest_patterns:
                    if re.search(pattern, model_id):
                        latest_models.append(model)
                        break

            return latest_models
    
    async def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific model.
        
        Args:
            model_id: The model identifier
            
        Returns:
            Model information dictionary or None if not found
        """
        models = await self.get_models()
        
        for model in models:
            if model.get("id") == model_id:
                return model
        
        return None
    
    async def get_models_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get models filtered by category.
        
        Args:
            category: Category name (e.g., "chat", "reasoning", "code")
            
        Returns:
            List of models in the specified category
        """
        models = await self.get_models()
        
        return [
            model for model in models
            if model.get("category", "").lower() == category.lower()
        ]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics and metadata.

        Returns:
            Dictionary with cache statistics
        """
        with self._cache_lock:
            if not isinstance(self._memory_cache, list):
                return {"total_models": 0, "error": "Cache not initialized"}

            # Count providers
            providers = set()
            vision_count = 0
            reasoning_count = 0

            for model in self._memory_cache:
                metadata = self.get_model_metadata(model.get("id", ""))

                provider = metadata.get("provider")
                if provider and provider != "Unknown":
                    providers.add(provider)

                caps = metadata.get("capabilities", {})
                if caps.get("supports_vision", False):
                    vision_count += 1

                # Check if model is a reasoning model
                model_id = model.get("id", "").lower()
                if "o1" in model_id or "reasoning" in metadata.get("description", "").lower():
                    reasoning_count += 1

            # Calculate cache size
            try:
                cache_json = json.dumps(self._memory_cache, ensure_ascii=False)
                cache_size_bytes = sys.getsizeof(cache_json)
                cache_size_mb = cache_size_bytes / (1024 * 1024)
            except Exception as e:
                logger.warning(f"Failed to calculate cache size: {e}")
                cache_size_mb = 0.0

            return {
                "total_models": len(self._memory_cache),
                "providers": sorted(list(providers)),
                "vision_capable_count": vision_count,
                "reasoning_model_count": reasoning_count,
                "cache_size_mb": round(cache_size_mb, 4),
                "last_updated": self._last_update.isoformat() if self._last_update else None,
                "is_expired": self.is_expired(),
                "ttl_seconds": self.ttl_seconds
            }

    def shutdown(self) -> None:
        """
        Shutdown the cache and clean up resources.

        This method should be called when the cache is no longer needed to
        ensure proper cleanup of the thread pool executor.
        """
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=True)
            logger.info("ModelCache executor shut down")

        if hasattr(self, '_transport') and self._transport is not None:
            self._transport.close()

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.shutdown()
        except Exception:
            pass  # Ignore errors during cleanup


# Client access moved to _fetch_models_from_api to avoid circular imports
