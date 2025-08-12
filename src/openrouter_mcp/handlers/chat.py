import os
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from ..client.openrouter import OpenRouterClient


# Create the MCP instance
mcp = FastMCP("OpenRouter MCP Server")


logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """A chat message."""
    role: str = Field(..., description="The role of the message sender (system, user, assistant)")
    content: str = Field(..., description="The content of the message")


class ChatCompletionRequest(BaseModel):
    """Request for chat completion."""
    model: str = Field(..., description="The model to use for completion")
    messages: List[ChatMessage] = Field(..., description="List of messages in the conversation")
    temperature: float = Field(0.7, description="Sampling temperature (0.0 to 2.0)")
    max_tokens: Optional[int] = Field(None, description="Maximum number of tokens to generate")
    stream: bool = Field(False, description="Whether to stream the response")


class ModelListRequest(BaseModel):
    """Request for listing available models."""
    filter_by: Optional[str] = Field(None, description="Filter models by name substring")


class UsageStatsRequest(BaseModel):
    """Request for usage statistics."""
    start_date: Optional[str] = Field(None, description="Start date for usage tracking (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date for usage tracking (YYYY-MM-DD)")


def get_openrouter_client() -> OpenRouterClient:
    """Get configured OpenRouter client."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")
    
    return OpenRouterClient.from_env()


@mcp.tool()
async def chat_with_model(request: ChatCompletionRequest) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
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
    
    # Convert Pydantic models to dict format expected by client
    messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    client = get_openrouter_client()
    
    try:
        async with client:
            if request.stream:
                logger.info("Initiating streaming chat completion")
                chunks = []
                async for chunk in client.stream_chat_completion(
                    model=request.model,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens
                ):
                    chunks.append(chunk)
                
                logger.info(f"Streaming completed with {len(chunks)} chunks")
                return chunks
            else:
                logger.info("Initiating non-streaming chat completion")
                response = await client.chat_completion(
                    model=request.model,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=False
                )
                
                logger.info(f"Chat completion successful, tokens used: {response.get('usage', {}).get('total_tokens', 'unknown')}")
                return response
                
    except Exception as e:
        logger.error(f"Chat completion failed: {str(e)}")
        raise


@mcp.tool()
async def list_available_models(request: ModelListRequest) -> List[Dict[str, Any]]:
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
    
    client = get_openrouter_client()
    
    try:
        async with client:
            models = await client.list_models(filter_by=request.filter_by)
            logger.info(f"Retrieved {len(models)} models")
            return models
            
    except Exception as e:
        logger.error(f"Failed to list models: {str(e)}")
        raise


@mcp.tool()
async def get_usage_stats(request: UsageStatsRequest) -> Dict[str, Any]:
    """
    Get API usage statistics from OpenRouter.
    
    This tool retrieves usage statistics for your OpenRouter API account,
    including total costs, token usage, and request counts. You can optionally
    specify a date range to get statistics for a specific period.
    
    Args:
        request: Usage stats request with optional date range
        
    Returns:
        Dictionary containing usage statistics:
        - total_cost: Total cost in USD
        - total_tokens: Total tokens used
        - requests: Number of API requests made
        - models: List of models used
        
    Raises:
        OpenRouterError: If the API request fails
        
    Example:
        request = UsageStatsRequest(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        stats = await get_usage_stats(request)
    """
    logger.info(f"Getting usage stats from {request.start_date or 'beginning'} to {request.end_date or 'now'}")
    
    client = get_openrouter_client()
    
    try:
        async with client:
            stats = await client.track_usage(
                start_date=request.start_date,
                end_date=request.end_date
            )
            logger.info(f"Retrieved usage stats: {stats.get('total_cost', 'unknown')} USD total cost")
            return stats
            
    except Exception as e:
        logger.error(f"Failed to get usage stats: {str(e)}")
        raise