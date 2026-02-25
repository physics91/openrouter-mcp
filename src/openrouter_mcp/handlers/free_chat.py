"""Free chat MCP tool handler -- zero-cost AI chat using free OpenRouter models."""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..mcp_registry import mcp, get_openrouter_client
from ..config.constants import FreeChatConfig, ModelDefaults
from ..free.router import FreeModelRouter
from ..client.openrouter import RateLimitError, OpenRouterError

logger = logging.getLogger(__name__)

_router: Optional[FreeModelRouter] = None


async def _get_router() -> FreeModelRouter:
    """Get or create the module-level FreeModelRouter singleton."""
    global _router
    if _router is None:
        client = await get_openrouter_client()
        _router = FreeModelRouter(client.model_cache)
    return _router


def reset_router() -> None:
    """Reset the router singleton. Called during shutdown or key rotation."""
    global _router
    _router = None


class FreeChatRequest(BaseModel):
    """Request for free chat completion."""

    message: str = Field(..., description="User message to send")
    system_prompt: str = Field("", description="System prompt (optional)")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list, description="Previous conversation messages"
    )
    max_tokens: int = Field(FreeChatConfig.MAX_TOKENS, description="Maximum tokens to generate")
    temperature: float = Field(ModelDefaults.TEMPERATURE, description="Sampling temperature")
    preferred_models: List[str] = Field(
        default_factory=list, description="Preferred free model IDs (optional override)"
    )


@mcp.tool()
async def free_chat(request: FreeChatRequest) -> Dict[str, Any]:
    """
    Chat using free OpenRouter models with automatic model selection.

    Automatically selects the best available free model based on quality scoring.
    If a model hits its rate limit, transparently falls back to the next best model.
    Cost is always $0.

    Args:
        request: Free chat request with message and optional parameters.

    Returns:
        Dictionary with model_used, response text, and usage info.
    """
    router = await _get_router()
    client = await get_openrouter_client()

    # Build messages
    messages: List[Dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.extend(request.conversation_history)
    messages.append({"role": "user", "content": request.message})

    last_error: Optional[Exception] = None

    for _attempt in range(FreeChatConfig.MAX_RETRY_COUNT + 1):
        try:
            model_id = await router.select_model(
                preferred_models=request.preferred_models or None
            )
        except RuntimeError:
            raise

        try:
            response = await client.chat_completion(
                model=model_id,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
            )

            content = ""
            choices = response.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")

            return {
                "model_used": model_id,
                "response": content,
                "usage": response.get("usage", {}),
            }

        except RateLimitError as e:
            logger.warning(f"Rate limit hit for {model_id}, trying next model")
            router.report_rate_limit(model_id)
            last_error = e
            continue

        except OpenRouterError as e:
            logger.error(f"OpenRouter error with model {model_id}: {e}")
            last_error = e
            router.report_rate_limit(model_id)
            continue

    raise last_error or RuntimeError("사용 가능한 free 모델이 없습니다.")


@mcp.tool()
async def list_free_models() -> Dict[str, Any]:
    """List all available free models with quality scores and availability status."""
    router = await _get_router()
    models_info = router.list_models_with_status()
    return {
        "models": models_info,
        "total_count": len(models_info),
        "available_count": sum(1 for m in models_info if m["available"]),
    }
