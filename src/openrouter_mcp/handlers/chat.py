# mypy: disable-error-code=untyped-decorator

import logging
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator

# Import shared MCP instance and client manager from registry
from ..mcp_registry import get_openrouter_client, mcp

# Import centralized configuration constants
from ..models.requests import BaseChatRequest
from ..runtime_thrift import (
    attach_thrift_metadata_from_payload,
    collect_stream_with_request_thrift_metadata,
    compact_messages_for_model,
    enrich_response_with_request_thrift_metadata,
    get_thrift_metrics_snapshot_for_dates,
    thrift_request_scope,
)
from ..utils.message_utils import serialize_messages

logger = logging.getLogger(__name__)


class ChatCompletionRequest(BaseChatRequest):
    """Request for chat completion."""


class ModelListRequest(BaseModel):
    """Request for listing available models."""

    filter_by: Optional[str] = Field(
        None, description="Filter models by name substring"
    )


class UsageStatsRequest(BaseModel):
    """Request for usage statistics."""

    start_date: Optional[str] = Field(
        None,
        description="Deprecated: arbitrary date ranges are unsupported; omit this field",
    )
    end_date: Optional[str] = Field(
        None,
        description="Deprecated: arbitrary date ranges are unsupported; omit this field",
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def reject_date_range(cls, value: str | None) -> None:
        if value is not None:
            raise ValueError(
                "API-key usage does not support arbitrary date ranges; omit start_date/end_date"
            )


async def _stream_chat_with_thrift_metadata(
    client: Any,
    request: ChatCompletionRequest,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collect a streaming chat response and enrich its final chunk."""
    logger.info("Initiating streaming chat completion")
    stream = client.stream_chat_completion(
        model=request.model,
        messages=messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    chunks = await collect_stream_with_request_thrift_metadata(
        client,
        request.model,
        stream,
        logger=logger,
        log_context="chat response",
    )

    logger.info(f"Streaming completed with {len(chunks)} chunks")
    return chunks


async def _complete_chat_with_thrift_metadata(
    client: Any,
    request: ChatCompletionRequest,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Complete a chat request and enrich the response with thrift metadata."""
    logger.info("Initiating non-streaming chat completion")
    response = await client.chat_completion(
        model=request.model,
        messages=messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=False,
    )
    if not isinstance(response, dict):
        raise ValueError("Invalid response format from chat completion")

    response = await enrich_response_with_request_thrift_metadata(
        client,
        request.model,
        response,
        logger=logger,
        log_context="chat response",
    )

    logger.info(
        f"Chat completion successful, tokens used: {response.get('usage', {}).get('total_tokens', 'unknown')}"
    )
    return response


@mcp.tool()
async def chat_with_model(
    request: ChatCompletionRequest,
) -> Union[dict[str, Any], list[dict[str, Any]]]:
    """
    Generate chat completion using OpenRouter API.

    This tool allows you to have conversations with various AI models through OpenRouter.
    You can specify the model, conversation messages, and various parameters like temperature.

    Args:
        request: Chat completion request containing model, messages, and parameters

    Returns:
        For non-streaming: Single response dictionary with choices and usage
        For streaming: List of response chunks

    Raises:
        ValueError: If request parameters are invalid
        OpenRouterError: If the API request fails

    Example:
        request = ChatCompletionRequest(
            model="openai/gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ],
            temperature=0.7
        )
        response = await chat_with_model(request)
    """
    logger.info(f"Processing chat completion request for model: {request.model}")

    with thrift_request_scope():
        # Convert Pydantic models to dict format expected by client
        messages = serialize_messages(request.messages)

        # Get shared client (already in async context, no need for 'async with')
        client = await get_openrouter_client()
        compaction = await compact_messages_for_model(
            client,
            request.model,
            messages,
            max_completion_tokens=request.max_tokens,
        )
        messages = compaction.messages

        try:
            if request.stream:
                return await _stream_chat_with_thrift_metadata(
                    client, request, messages
                )
            return await _complete_chat_with_thrift_metadata(client, request, messages)

        except Exception as e:
            logger.error(f"Chat completion failed: {e!s}")
            raise


@mcp.tool()
async def list_available_models(request: ModelListRequest) -> list[dict[str, Any]]:
    """
    List all available models from OpenRouter.

    This tool retrieves information about all AI models available through OpenRouter,
    including their pricing, capabilities, and context limits. You can optionally
    filter the results by model name.

    Args:
        request: Model list request with optional filter

    Returns:
        List of dictionaries containing model information:
        - id: Model identifier (e.g., "openai/gpt-4")
        - name: Human-readable model name
        - description: Model description
        - pricing: Cost per token for prompts and completions
        - context_length: Maximum context window size
        - architecture: Model architecture details

    Raises:
        OpenRouterError: If the API request fails

    Example:
        request = ModelListRequest(filter_by="gpt")
        models = await list_available_models(request)
    """
    logger.info(f"Listing models with filter: {request.filter_by or 'none'}")

    # Get shared client (already in async context, no need for 'async with')
    client = await get_openrouter_client()

    try:
        models = await client.list_models(filter_by=request.filter_by)
        models = [model for model in models if isinstance(model, dict)]
        logger.info(f"Retrieved {len(models)} models")
        return models

    except Exception as e:
        logger.error(f"Failed to list models: {e!s}")
        raise


@mcp.tool()
async def get_usage_stats(request: UsageStatsRequest) -> dict[str, Any]:
    """
    Get spending counters for the authenticated OpenRouter API key.

    Returns cumulative spending and current UTC day/week/month counters from
    GET /key, plus separately scoped local runtime thrift savings. Arbitrary
    start_date/end_date ranges are rejected. This is not account-wide activity.

    Args:
        request: Usage stats request; omit start_date and end_date

    Returns:
        Dictionary containing usage statistics:
        - total_cost: Total cost in USD
        - scope: api_key
        - usage_daily/usage_weekly/usage_monthly: Current UTC-period spending
        - total_tokens/requests/models: null (not provided by this endpoint)

    Raises:
        OpenRouterError: If the API request fails

    Example:
        request = UsageStatsRequest()
        stats = await get_usage_stats(request)
    """
    logger.info(
        f"Getting usage stats from {request.start_date or 'beginning'} to {request.end_date or 'now'}"
    )

    # Get shared client (already in async context, no need for 'async with')
    client = await get_openrouter_client()

    try:
        stats = await client.track_usage(
            start_date=request.start_date, end_date=request.end_date
        )
        if not isinstance(stats, dict):
            raise ValueError("Invalid usage stats response format")
        stats = dict(stats)
        stats["thrift_scope"] = "local_runtime"
        thrift_metrics = get_thrift_metrics_snapshot_for_dates(
            request.start_date,
            request.end_date,
        )
        stats = attach_thrift_metadata_from_payload(stats, thrift_metrics)
        if stats.get("scope") == "api_key":
            # Local savings and key-wide spending may cover different clients,
            # credentials, and periods; combining them would invent a savings rate.
            stats["thrift_summary"]["estimated_cost_without_thrift_usd"] = None
            stats["thrift_summary"]["effective_cost_reduction_pct"] = None
            for name in ("cache_hit_request_rate_pct", "cache_write_request_rate_pct"):
                stats["thrift_summary"]["cache_efficiency"][name] = None
        logger.info(
            f"Retrieved usage stats: {stats.get('total_cost', 'unknown')} USD total cost"
        )
        return stats

    except Exception as e:
        logger.error(f"Failed to get usage stats: {e!s}")
        raise
