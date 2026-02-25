import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
import json as json_lib

# Import ModelCache for intelligent caching
from ..models.cache import ModelCache
# Import centralized configuration constants
from ..config.constants import APIConfig, CacheConfig, EnvVars, ModelDefaults
# Import sanitizer from utils (extracted for SRP compliance)
from ..utils.sanitizer import SensitiveDataSanitizer
from ..utils.http import build_openrouter_headers
from ..utils.pricing import normalize_pricing
from ..utils.async_utils import maybe_await
from ..utils.env import get_env_value, get_required_env


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


# Note: SensitiveDataSanitizer has been moved to openrouter_mcp.utils.sanitizer
# for SRP compliance. Import it from there for new code.
# The import at module level provides backward compatibility.


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
        base_url: str = APIConfig.BASE_URL,
        app_name: Optional[str] = None,
        http_referer: Optional[str] = None,
        timeout: float = APIConfig.DEFAULT_TIMEOUT,
        logger: Optional[logging.Logger] = None,
        enable_cache: bool = True,
        cache_ttl: int = CacheConfig.DEFAULT_TTL_SECONDS,
        enable_verbose_logging: bool = False
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
            enable_verbose_logging: If True, log truncated request/response content.
                                   If False (default), only log metadata.
                                   WARNING: Even with this enabled, sensitive data is sanitized,
                                   but truncated prompts/responses may still contain PII.

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
        self.enable_verbose_logging = enable_verbose_logging

        # Log warning if verbose logging is enabled
        if self.enable_verbose_logging:
            self.logger.warning(
                "Verbose logging is enabled. Truncated request/response content will be logged. "
                "This may include sensitive information. Use only for debugging."
            )

        self._client = httpx.AsyncClient(timeout=timeout)

        # Initialize model cache with client credentials
        if enable_cache:
            # Convert seconds to hours for ModelCache (using float for sub-hour precision)
            # Minimum TTL to prevent too-frequent refreshes
            ttl_hours = max(CacheConfig.MIN_TTL_HOURS, cache_ttl / 3600.0)
            self._model_cache = ModelCache(
                ttl_hours=ttl_hours,
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            self._model_cache = None

    @property
    def model_cache(self) -> "ModelCache":
        """Public accessor for the model cache."""
        return self._model_cache

    @classmethod
    def from_env(cls) -> "OpenRouterClient":
        """Create client from environment variables."""
        api_key = get_required_env(EnvVars.API_KEY)
        return cls(
            api_key=api_key,
            base_url=get_env_value(EnvVars.BASE_URL, APIConfig.BASE_URL),
            app_name=get_env_value(EnvVars.APP_NAME),
            http_referer=get_env_value(EnvVars.HTTP_REFERER)
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        return build_openrouter_headers(
            self.api_key,
            app_name=self.app_name,
            http_referer=self.http_referer,
            fallback_to_env=False,
        )
    
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

    def _validate_messages_if_text(self, messages: List[Dict[str, Any]]) -> None:
        """Validate messages when they are simple text-only payloads."""
        if messages and all(isinstance(msg.get("content"), str) for msg in messages):
            self._validate_messages(messages)  # type: ignore[arg-type]

    def _build_chat_payload(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
        stream: bool,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Build a chat completion payload with shared validation."""
        self._validate_model(model)
        self._validate_messages_if_text(messages)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            **kwargs,
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        return payload

    def _log_request(
        self,
        method_label: str,
        url: str,
        headers: Dict[str, str],
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log sanitized request details."""
        sanitized_headers = SensitiveDataSanitizer.sanitize_headers(headers)
        self.logger.debug(f"Making {method_label} request to {url}")
        self.logger.debug(f"Request headers: {sanitized_headers}")
        if payload:
            sanitized_payload = SensitiveDataSanitizer.sanitize_payload(
                payload, enable_verbose=self.enable_verbose_logging
            )
            self.logger.debug(f"Request payload: {sanitized_payload}")
        if params:
            self.logger.debug(f"Request params: {params}")

    def _handle_request_error(self, e: Exception, context: str, url: str) -> None:
        """Handle non-HTTP request errors (connect, timeout, generic)."""
        if isinstance(e, httpx.ConnectError):
            self.logger.error(f"Connection error for {context} {url}: {str(e)}")
            raise OpenRouterError(
                "Network error: Failed to connect to OpenRouter API"
            ) from e
        if isinstance(e, httpx.TimeoutException):
            self.logger.error(f"Timeout error for {context} {url}: {str(e)}")
            raise OpenRouterError(
                f"Request timeout after {self.timeout} seconds"
            ) from e
        self.logger.error(f"Unexpected error for {context} {url}: {str(e)}")
        raise OpenRouterError(f"Unexpected error: {str(e)}") from e

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
        self._log_request(method, url, headers, payload=json, params=params)

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                params=params
            )

            self.logger.debug(f"Response status: {response.status_code}")
            await maybe_await(response.raise_for_status())

            response_data = await maybe_await(response.json())

            # Sanitize response for logging
            if isinstance(response_data, dict):
                if "choices" in response_data or "data" in response_data:
                    # This looks like a completion or model list response
                    if "choices" in response_data:
                        sanitized_response = SensitiveDataSanitizer.sanitize_response(
                            response_data, enable_verbose=self.enable_verbose_logging
                        )
                        self.logger.debug(f"Response data: {sanitized_response}")
                    else:
                        # For non-completion responses (like model lists), log keys only
                        self.logger.debug(f"Response data keys: {list(response_data.keys())}")
                else:
                    self.logger.debug(f"Response data keys: {list(response_data.keys())}")
            else:
                self.logger.debug("Response data type: non-dict response")

            return response_data

        except httpx.HTTPStatusError as e:
            self.logger.warning(f"HTTP error {e.response.status_code} for {method} {url}")
            await self._handle_http_error(e.response)
        except Exception as e:
            self._handle_request_error(e, method, url)

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
        self._log_request("streaming POST", url, headers, payload=json_data)

        try:
            async with self._client.stream(
                "POST",
                url,
                headers=headers,
                json=json_data
            ) as response:
                self.logger.debug(f"Stream response status: {response.status_code}")
                await maybe_await(response.raise_for_status())      

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

                            # Log chunk metadata only (don't log content even in verbose mode for streaming)
                            if chunk_count % 10 == 1:  # Log every 10th chunk to reduce noise
                                self.logger.debug(
                                    f"Streaming chunk {chunk_count} "
                                    f"(keys: {list(chunk.keys()) if isinstance(chunk, dict) else 'non-dict'})"
                                )

                            yield chunk
                        except json_lib.JSONDecodeError as e:
                            # Don't log the actual data content - could contain sensitive info
                            self.logger.warning(
                                f"Failed to parse stream chunk (length: {len(data)}): {str(e)}"
                            )
                            continue

        except httpx.HTTPStatusError as e:
            self.logger.warning(f"HTTP error {e.response.status_code} for streaming POST {url}")
            await self._handle_http_error(e.response)
        except Exception as e:
            self._handle_request_error(e, "streaming POST", url)
    
    async def _handle_http_error(self, response: httpx.Response) -> None:
        """Handle HTTP errors from OpenRouter API.

        SECURITY: Response bodies are sanitized to prevent leaking sensitive data in error messages.
        """
        try:
            error_data = await maybe_await(response.json())
            error_message = error_data.get("error", {}).get("message", "Unknown error")
        except (json_lib.JSONDecodeError, KeyError):
            # SECURITY: Don't include raw response.text - it may contain sensitive data
            # Truncate and sanitize the response body
            response_preview = SensitiveDataSanitizer.truncate_content(
                response.text, max_length=100
            ) if response.text else "No response body"
            error_message = f"HTTP {response.status_code}: {response_preview}"

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
        use_cache: bool = True,
        _bypass_cache: bool = False
    ) -> List[Dict[str, Any]]:
        """List available models from OpenRouter.

        Retrieves a list of all available AI models, optionally filtered by name.
        Each model includes information about pricing, context length, and capabilities.

        Args:
            filter_by: Optional string to filter model names (case-insensitive)
            use_cache: Whether to use cached models if available
            _bypass_cache: Internal flag to bypass cache (prevents recursion)

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
        # Use cache system if enabled and not explicitly bypassed
        if use_cache and self._model_cache and not _bypass_cache:
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

    async def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get normalized pricing for a specific model.

        Pricing values are normalized to per-token dollars to ensure consistent
        cost calculations across the codebase.
        """
        self._validate_model(model)
        pricing: Dict[str, Any] = {}

        try:
            if self._model_cache:
                model_info = await self._model_cache.get_model_info(model)
            else:
                model_info = await self.get_model_info(model)

            if model_info and "pricing" in model_info:
                pricing = model_info["pricing"]
        except Exception as e:
            self.logger.warning(f"Failed to fetch pricing for model {model}: {e}")

        return normalize_pricing(pricing)
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = ModelDefaults.TEMPERATURE,
        max_tokens: Optional[int] = ModelDefaults.MAX_TOKENS,
        stream: bool = ModelDefaults.STREAM,
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
        payload = self._build_chat_payload(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            **kwargs,
        )

        return await self._make_request("POST", "/chat/completions", json=payload)
    
    async def stream_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = ModelDefaults.TEMPERATURE,
        max_tokens: Optional[int] = ModelDefaults.MAX_TOKENS,
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
        payload = self._build_chat_payload(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in self._stream_request("/chat/completions", payload):
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
            self._model_cache.clear()
            self.logger.info("Model cache cleared")
    
    async def __aenter__(self) -> "OpenRouterClient":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
