import os
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import httpx
import json as json_lib
from contextlib import asynccontextmanager

# Import ModelCache for intelligent caching
from ..models.cache import ModelCache


class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors."""
    pass


class AuthenticationError(OpenRouterError):
    """Raised when API key is invalid or missing."""
    pass


class RateLimitError(OpenRouterError):
    """Raised when rate limit is exceeded."""
    pass


class InvalidRequestError(OpenRouterError):
    """Raised when request is invalid."""
    pass


class OpenRouterClient:
    """Client for OpenRouter API.
    
    This client provides async methods to interact with the OpenRouter API,
    including model listing, chat completions, and usage tracking.
    
    Example:
        >>> async with OpenRouterClient(api_key="your-key") as client:
        ...     models = await client.list_models()
        ...     response = await client.chat_completion(
        ...         model="openai/gpt-4",
        ...         messages=[{"role": "user", "content": "Hello!"}]
        ...     )
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        app_name: Optional[str] = None,
        http_referer: Optional[str] = None,
        timeout: float = 30.0,
        logger: Optional[logging.Logger] = None,
        enable_cache: bool = True,
        cache_ttl: int = 3600
    ) -> None:
        """Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key
            base_url: Base URL for OpenRouter API
            app_name: Application name for tracking
            http_referer: HTTP referer for tracking
            timeout: Request timeout in seconds
            logger: Custom logger instance
            enable_cache: Whether to enable model caching
            cache_ttl: Cache time-to-live in seconds
            
        Raises:
            ValueError: If API key is empty or None
        """
        if not api_key or api_key.strip() == "":
            raise ValueError("API key is required")
        
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.app_name = app_name
        self.http_referer = http_referer
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)
        self.enable_cache = enable_cache
        
        self._client = httpx.AsyncClient(timeout=timeout)
        
        # Initialize model cache
        if enable_cache:
            # Convert seconds to hours for ModelCache
            ttl_hours = max(1, cache_ttl // 3600)  # Minimum 1 hour
            self._model_cache = ModelCache(ttl_hours=ttl_hours)
        else:
            self._model_cache = None
    
    @classmethod
    def from_env(cls) -> "OpenRouterClient":
        """Create client from environment variables."""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        
        return cls(
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            app_name=os.getenv("OPENROUTER_APP_NAME"),
            http_referer=os.getenv("OPENROUTER_HTTP_REFERER")
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if self.app_name:
            headers["X-Title"] = self.app_name
        
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        
        return headers
    
    def _validate_model(self, model: str) -> None:
        """Validate model parameter."""
        if not model or model.strip() == "":
            raise ValueError("Model cannot be empty")
    
    def _validate_messages(self, messages: List[Dict[str, str]]) -> None:
        """Validate messages parameter."""
        if not messages:
            raise ValueError("Messages cannot be empty")
        
        valid_roles = {"system", "user", "assistant"}
        
        for message in messages:
            if "role" not in message or "content" not in message:
                raise ValueError("Message must have 'role' and 'content' fields")
            
            if message["role"] not in valid_roles:
                raise ValueError(f"Invalid role: {message['role']}. Must be one of {valid_roles}")
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to OpenRouter API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            json: JSON payload for POST/PUT requests
            params: URL parameters
            
        Returns:
            Response data as dictionary
            
        Raises:
            OpenRouterError: For API errors, network issues, or unexpected errors
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        self.logger.debug(f"Making {method} request to {url}")
        if json:
            self.logger.debug(f"Request payload: {json}")
        if params:
            self.logger.debug(f"Request params: {params}")
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                params=params
            )
            
            self.logger.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            
            response_data = response.json()
            self.logger.debug(f"Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'non-dict response'}")
            
            return response_data
        
        except httpx.HTTPStatusError as e:
            self.logger.warning(f"HTTP error {e.response.status_code} for {method} {url}")
            await self._handle_http_error(e.response)
        except httpx.ConnectError as e:
            self.logger.error(f"Connection error for {method} {url}: {str(e)}")
            raise OpenRouterError("Network error: Failed to connect to OpenRouter API")
        except httpx.TimeoutException as e:
            self.logger.error(f"Timeout error for {method} {url}: {str(e)}")
            raise OpenRouterError(f"Request timeout after {self.timeout} seconds")
        except Exception as e:
            self.logger.error(f"Unexpected error for {method} {url}: {str(e)}")
            raise OpenRouterError(f"Unexpected error: {str(e)}")
    
    async def _stream_request(
        self,
        endpoint: str,
        json_data: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Make streaming request to OpenRouter API.
        
        Args:
            endpoint: API endpoint path
            json_data: JSON payload for the request
            
        Yields:
            Streaming response chunks as dictionaries
            
        Raises:
            OpenRouterError: For API errors, network issues, or unexpected errors
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        self.logger.debug(f"Making streaming POST request to {url}")
        self.logger.debug(f"Stream payload: {json_data}")
        
        try:
            async with self._client.stream(
                "POST",
                url,
                headers=headers,
                json=json_data
            ) as response:
                self.logger.debug(f"Stream response status: {response.status_code}")
                response.raise_for_status()
                
                chunk_count = 0
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data.strip() == "[DONE]":
                            self.logger.debug(f"Stream completed after {chunk_count} chunks")
                            break
                        try:
                            chunk = json_lib.loads(data)
                            chunk_count += 1
                            self.logger.debug(f"Yielding chunk {chunk_count}")
                            yield chunk
                        except json_lib.JSONDecodeError as e:
                            self.logger.warning(f"Failed to parse stream chunk: {data[:100]}...")
                            continue
        
        except httpx.HTTPStatusError as e:
            self.logger.warning(f"HTTP error {e.response.status_code} for streaming POST {url}")
            await self._handle_http_error(e.response)
        except httpx.ConnectError as e:
            self.logger.error(f"Connection error for streaming POST {url}: {str(e)}")
            raise OpenRouterError("Network error: Failed to connect to OpenRouter API")
        except httpx.TimeoutException as e:
            self.logger.error(f"Timeout error for streaming POST {url}: {str(e)}")
            raise OpenRouterError(f"Request timeout after {self.timeout} seconds")
        except Exception as e:
            self.logger.error(f"Unexpected error for streaming POST {url}: {str(e)}")
            raise OpenRouterError(f"Unexpected error: {str(e)}")
    
    async def _handle_http_error(self, response: httpx.Response) -> None:
        """Handle HTTP errors from OpenRouter API."""
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Unknown error")
        except (json_lib.JSONDecodeError, KeyError):
            error_message = f"HTTP {response.status_code}: {response.text}"
        
        if response.status_code == 401:
            raise AuthenticationError(error_message)
        elif response.status_code == 429:
            raise RateLimitError(error_message)
        elif response.status_code == 400:
            raise InvalidRequestError(error_message)
        else:
            raise OpenRouterError(f"API error: {error_message}")
    
    async def list_models(
        self,
        filter_by: Optional[str] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """List available models from OpenRouter.
        
        Retrieves a list of all available AI models, optionally filtered by name.
        Each model includes information about pricing, context length, and capabilities.
        
        Args:
            filter_by: Optional string to filter model names (case-insensitive)
            use_cache: Whether to use cached models if available
            
        Returns:
            List of dictionaries containing model information with keys:
            - id: Model identifier (e.g., "openai/gpt-4")
            - name: Human-readable model name
            - description: Model description
            - pricing: Dictionary with prompt/completion pricing
            - context_length: Maximum context window size
            - architecture: Model architecture details
            
        Raises:
            OpenRouterError: If the API request fails
            
        Example:
            >>> models = await client.list_models()
            >>> gpt_models = await client.list_models(filter_by="gpt")
        """
        # Use cache system if enabled
        if use_cache and self._model_cache:
            try:
                all_models = await self._model_cache.get_models()
                if all_models:
                    self.logger.info(f"Retrieved {len(all_models)} models from cache")
                    
                    # Apply filter if specified
                    if filter_by:
                        filter_lower = filter_by.lower()
                        filtered_models = [
                            model for model in all_models 
                            if filter_lower in model.get("name", "").lower() 
                            or filter_lower in model.get("id", "").lower()
                        ]
                        self.logger.info(f"Filtered to {len(filtered_models)} models")
                        return filtered_models
                    else:
                        return all_models
            except Exception as e:
                self.logger.warning(f"Failed to get cached models: {e}")
                # Continue to API fetch
        
        # Fallback: Fetch directly from API if cache is disabled or failed
        self.logger.info(f"Fetching models directly from API with filter: {filter_by or 'none'}")
        
        params = {}
        if filter_by:
            params["filter"] = filter_by
            
        response = await self._make_request("GET", "/models", params=params)
        models = response.get("data", [])
        
        self.logger.info(f"Retrieved {len(models)} models from API")
        return models
    
    async def get_model_info(self, model: str) -> Dict[str, Any]:
        """Get information about a specific model.
        
        Args:
            model: Model identifier (e.g., "openai/gpt-4")
            
        Returns:
            Model information dictionary
        """
        self._validate_model(model)
        return await self._make_request("GET", f"/models/{model}")
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a chat completion.
        
        Args:
            model: Model to use
            messages: List of message dictionaries (can include image content)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional parameters
            
        Returns:
            Chat completion response
        """
        self._validate_model(model)
        # Skip message validation for multimodal messages (they have different structure)
        if messages and all(isinstance(msg.get("content"), str) for msg in messages):
            self._validate_messages(messages)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            **kwargs
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        return await self._make_request("POST", "/chat/completions", json=payload)
    
    async def chat_completion_with_vision(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a chat completion with vision/image support.
        
        This method specifically handles messages that contain images,
        properly formatting them for vision-capable models.
        
        Args:
            model: Vision-capable model to use
            messages: List of message dictionaries with potential image content
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional parameters
            
        Returns:
            Chat completion response
            
        Example:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in this image?"},
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
                    ]
                }
            ]
        """
        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            **kwargs
        )
    
    async def stream_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Create a streaming chat completion.
        
        Args:
            model: Model to use
            messages: List of message dictionaries (can include image content)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Yields:
            Chat completion chunks
        """
        self._validate_model(model)
        # Skip message validation for multimodal messages
        if messages and all(isinstance(msg.get("content"), str) for msg in messages):
            self._validate_messages(messages)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        async for chunk in self._stream_request("/chat/completions", payload):
            yield chunk
    
    async def stream_chat_completion_with_vision(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Create a streaming chat completion with vision support.
        
        Args:
            model: Vision-capable model to use
            messages: List of message dictionaries with potential image content
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Yields:
            Chat completion chunks
        """
        async for chunk in self.stream_chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            yield chunk
    
    async def track_usage(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Track API usage statistics.
        
        Args:
            start_date: Start date for usage tracking (YYYY-MM-DD)
            end_date: End date for usage tracking (YYYY-MM-DD)
            
        Returns:
            Usage statistics dictionary
        """
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        return await self._make_request("GET", "/generation", params=params)
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
    
    def get_cache_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the model cache.
        
        Returns:
            Cache information dictionary or None if cache is disabled.
        """
        if self._model_cache:
            return self._model_cache.get_cache_stats()
        return None
    
    async def clear_cache(self) -> None:
        """Clear the model cache."""
        if self._model_cache:
            # Clear memory cache
            self._model_cache._memory_cache = []
            self._model_cache._last_update = None
            self.logger.info("Model cache cleared")
    
    async def __aenter__(self) -> "OpenRouterClient":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()