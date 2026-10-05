# mypy: disable-error-code=untyped-decorator

import base64
import io
import logging
from typing import Any, Optional, Union

from PIL import Image
from pydantic import BaseModel, Field, field_validator

from ..config.constants import ImageProcessingConfig

# Import shared MCP instance and client manager from registry
from ..mcp_registry import get_openrouter_client, mcp

# Import centralized request base classes
from ..models.requests import BaseChatRequest
from ..runtime_thrift import (
    collect_stream_with_request_thrift_metadata,
    enrich_response_with_request_thrift_metadata,
    thrift_request_scope,
)
from ..utils.message_utils import serialize_messages

logger = logging.getLogger(__name__)


class ImageInput(BaseModel):
    """Input for an image in multimodal requests.

    Security Note: File path access has been removed to prevent arbitrary file read vulnerabilities.
    Images must be provided as base64-encoded data or URLs only.
    """

    data: str = Field(..., description="Image data (base64 string or URL)")
    type: str = Field(..., description="Type of image data: 'base64' or 'url'")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ["base64", "url"]:
            raise ValueError(
                "Type must be 'base64' or 'url'. File path access is not supported for security reasons."
            )
        return v


class VisionChatRequest(BaseChatRequest):
    """Request for chat completion with vision."""

    images: list[ImageInput] = Field(..., description="List of images to analyze")


class VisionModelRequest(BaseModel):
    """Request for listing vision-capable models."""

    filter_by: Optional[str] = Field(
        None, description="Filter models by name substring"
    )


def encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Encode image bytes to base64 string.

    Security Note: This function only accepts image bytes, not file paths.
    File path support was removed to prevent arbitrary file read vulnerabilities.
    Callers must read files themselves and pass the bytes.

    Args:
        image_bytes: Image data as bytes

    Returns:
        Base64 encoded string of the image

    Raises:
        TypeError: If image_input is not bytes
        Exception: If the image cannot be processed
    """
    try:
        if not isinstance(image_bytes, bytes):
            raise TypeError(
                "encode_image_to_base64() only accepts bytes. "
                "File path support has been removed for security reasons. "
                "Please read the file yourself and pass the bytes."
            )

        return base64.b64encode(image_bytes).decode("utf-8")

    except Exception as e:
        logger.error(f"Failed to encode image to base64: {e!s}")
        raise


def validate_image_format(format_name: str) -> bool:
    """
    Validate if image format is supported.

    Args:
        format_name: Image format (e.g., 'JPEG', 'PNG')

    Returns:
        True if format is supported, False otherwise
    """
    return format_name.upper() in ImageProcessingConfig.SUPPORTED_FORMATS


def _optimize_image_to_limit(
    image: Image.Image, original_format: str, max_size_bytes: float
) -> str:
    """Compress and resize a validated image toward the requested size limit."""
    if not validate_image_format(original_format):
        logger.info(f"Converting unsupported format {original_format} to JPEG")
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            image_for_paste: Image.Image = (
                image.convert("RGBA") if image.mode == "P" else image
            )
            background.paste(
                image_for_paste,
                mask=(
                    image_for_paste.split()[-1]
                    if image_for_paste.mode in ("RGBA", "LA")
                    else None
                ),
            )
            image = background
        original_format = "JPEG"

    quality = 85
    while quality > 20:
        buffer = io.BytesIO()
        image.save(buffer, format=original_format, quality=quality, optimize=True)

        if len(buffer.getvalue()) <= max_size_bytes:
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        quality -= 15

    width, height = image.size
    resize_ratio = 0.8

    while resize_ratio > 0.3:
        new_width = int(width * resize_ratio)
        new_height = int(height * resize_ratio)

        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        resized_image.save(buffer, format=original_format, quality=75, optimize=True)

        if len(buffer.getvalue()) <= max_size_bytes:
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        resize_ratio -= 0.1

    buffer = io.BytesIO()
    resized_image = image.resize(
        (int(width * 0.3), int(height * 0.3)), Image.Resampling.LANCZOS
    )
    resized_image.save(buffer, format=original_format, quality=50, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _open_validated_image(
    image_bytes: bytes,
    max_size_bytes: float,
) -> tuple[Image.Image, str]:
    """Open decoded image bytes after enforcing resource safety limits."""
    safe_limit = max(max_size_bytes * 5, 1024 * 1024)
    if len(image_bytes) > safe_limit:
        raise ValueError(
            f"Decoded image too large: {len(image_bytes)} bytes exceeds safe limit"
        )

    image: Image.Image = Image.open(
        io.BytesIO(image_bytes), formats=ImageProcessingConfig.SUPPORTED_FORMATS
    )

    width, height = image.size
    if width * height > ImageProcessingConfig.MAX_PIXELS:
        raise ValueError(
            f"Image dimensions too large: {width}x{height} = {width*height} pixels exceeds {ImageProcessingConfig.MAX_PIXELS} pixels"
        )
    if (
        width > ImageProcessingConfig.MAX_DIMENSION
        or height > ImageProcessingConfig.MAX_DIMENSION
    ):
        raise ValueError(
            f"Image dimension too large: {width}x{height}, max dimension is {ImageProcessingConfig.MAX_DIMENSION}"
        )

    original_format = image.format
    if not original_format:
        original_format = "JPEG"
        logger.warning("Image format not detected, defaulting to JPEG")

    return image, original_format


def process_image(
    base64_data: str, max_size_mb: int = ImageProcessingConfig.MAX_SIZE_MB
) -> tuple[str, bool]:
    """
    Process an image: resize if too large, optimize for API usage.

    Args:
        base64_data: Base64 encoded image data
        max_size_mb: Maximum size in MB (default: 20MB)

    Returns:
        Tuple of (processed_base64_data, was_resized)

    Raises:
        ValueError: If image is too large or has invalid dimensions
        Exception: If image processing fails
    """
    # Security: Limit maximum base64 string size before decoding (prevents decompression bombs)
    if len(base64_data) > ImageProcessingConfig.MAX_BASE64_SIZE:
        raise ValueError(
            f"Base64 data too large: {len(base64_data)} bytes exceeds {ImageProcessingConfig.MAX_BASE64_SIZE} bytes"
        )

    try:
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)
        max_size_bytes = max_size_mb * 1024 * 1024
        image, original_format = _open_validated_image(image_bytes, max_size_bytes)

        # If image is already small enough, return early
        if len(image_bytes) <= max_size_bytes:
            return base64_data, False

        return _optimize_image_to_limit(image, original_format, max_size_bytes), True

    except Exception as e:
        logger.error(f"Failed to process image: {e!s}")
        raise


def format_vision_message(
    text: str,
    image_data: Optional[str] = None,
    image_type: Optional[str] = None,
    images: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """
    Format a message for vision models with OpenAI-compatible structure.

    Args:
        text: The text prompt
        image_data: Single image data (base64 or URL)
        image_type: Type of single image ('base64' or 'url')
        images: List of image dictionaries with 'data' and 'type' keys

    Returns:
        Formatted message dictionary
    """
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]

    # Handle single image
    if image_data and image_type:
        if image_type == "base64":
            image_url = f"data:image/jpeg;base64,{image_data}"
        else:
            image_url = image_data

        content.append({"type": "image_url", "image_url": {"url": image_url}})

    # Handle multiple images
    if images:
        for img in images:
            if img["type"] == "base64":
                image_url = f"data:image/jpeg;base64,{img['data']}"
            else:
                image_url = img["data"]

            content.append({"type": "image_url", "image_url": {"url": image_url}})

    return {"role": "user", "content": content}


def is_vision_model(model_info: dict[str, Any]) -> bool:
    """
    Check if a model supports vision/image input.

    Args:
        model_info: Model information dictionary

    Returns:
        True if model supports image input, False otherwise
    """
    architecture = model_info.get("architecture", {})
    input_modalities = architecture.get("input_modalities", [])
    return "image" in input_modalities


def filter_vision_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Filter a list of models to return only vision-capable ones.

    Args:
        models: List of model information dictionaries

    Returns:
        List of vision-capable models
    """
    return [model for model in models if is_vision_model(model)]


def get_vision_model_names(models: list[dict[str, Any]]) -> list[str]:
    """
    Get names of vision-capable models.

    Args:
        models: List of model information dictionaries

    Returns:
        List of vision model names
    """
    vision_models = filter_vision_models(models)
    return [model.get("name", model.get("id", "Unknown")) for model in vision_models]


def _build_vision_messages(
    base_messages: list[dict[str, Any]],
    images: list[ImageInput],
) -> list[dict[str, Any]]:
    if not base_messages:
        return []

    processed_images = []
    for image in images:
        if image.type == "base64":
            processed_data, was_resized = process_image(image.data)
            if was_resized:
                logger.info("Image was resized for API optimization")
            processed_images.append({"data": processed_data, "type": "base64"})
        else:
            processed_images.append({"data": image.data, "type": "url"})

    return [
        *base_messages[:-1],
        format_vision_message(
            text=base_messages[-1]["content"],
            images=processed_images,
        ),
    ]


async def _stream_vision_chat_with_thrift_metadata(
    client: Any,
    request: VisionChatRequest,
    vision_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collect a streaming vision response and enrich its final chunk."""
    logger.info("Initiating streaming vision chat completion")
    stream = client.stream_chat_completion(
        model=request.model,
        messages=vision_messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    chunks = await collect_stream_with_request_thrift_metadata(
        client,
        request.model,
        stream,
        logger=logger,
        log_context="vision response",
    )

    logger.info(f"Streaming completed with {len(chunks)} chunks")
    return chunks


async def _complete_vision_chat_with_thrift_metadata(
    client: Any,
    request: VisionChatRequest,
    vision_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Complete a vision request and enrich its response with thrift metadata."""
    logger.info("Initiating non-streaming vision chat completion")
    response = await client.chat_completion(
        model=request.model,
        messages=vision_messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    if not isinstance(response, dict):
        raise ValueError("Invalid response format from vision chat completion")

    response = await enrich_response_with_request_thrift_metadata(
        client,
        request.model,
        response,
        logger=logger,
        log_context="vision response",
    )

    logger.info("Vision chat completion successful")
    return response


@mcp.tool()
async def chat_with_vision(
    request: VisionChatRequest,
) -> Union[dict[str, Any], list[dict[str, Any]]]:
    """
    Generate chat completion with vision capabilities using OpenRouter API.

    This tool allows you to have conversations with vision-capable AI models,
    sending both text and images. The images can be provided as base64-encoded
    data or as URLs.

    Args:
        request: Vision chat request containing model, messages, images, and parameters

    Returns:
        For non-streaming: Single response dictionary with choices and usage
        For streaming: List of response chunks

    Raises:
        ValueError: If request parameters are invalid
        OpenRouterError: If the API request fails

    Example:
        request = VisionChatRequest(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "What's in this image?"}],
            images=[ImageInput(data="base64_string", type="base64")]
        )
        response = await chat_with_vision(request)
    """
    logger.info(f"Processing vision chat request for model: {request.model}")

    with thrift_request_scope():
        # Get shared client (already in async context, no need for 'async with')
        client = await get_openrouter_client()

        try:
            # Process images and create vision messages
            base_messages = serialize_messages(request.messages)
            vision_messages = _build_vision_messages(base_messages, request.images)

            if request.stream:
                return await _stream_vision_chat_with_thrift_metadata(
                    client, request, vision_messages
                )
            return await _complete_vision_chat_with_thrift_metadata(
                client, request, vision_messages
            )

        except Exception as e:
            logger.error(f"Vision chat completion failed: {e!s}")
            raise


@mcp.tool()
async def list_vision_models(request: VisionModelRequest) -> list[dict[str, Any]]:
    """
    List all vision-capable models from OpenRouter.

    This tool retrieves information about AI models that support image input,
    filtering out text-only models. You can optionally filter the results
    by model name.

    Args:
        request: Vision model list request with optional filter

    Returns:
        List of dictionaries containing vision model information:
        - id: Model identifier (e.g., "openai/gpt-4o")
        - name: Human-readable model name
        - description: Model description
        - architecture: Model capabilities including input modalities

    Raises:
        OpenRouterError: If the API request fails

    Example:
        request = VisionModelRequest(filter_by="gpt")
        models = await list_vision_models(request)
    """
    logger.info(f"Listing vision models with filter: {request.filter_by or 'none'}")

    # Get shared client (already in async context, no need for 'async with')
    client = await get_openrouter_client()

    try:
        # Get all models
        all_models = await client.list_models(filter_by=request.filter_by)

        # Filter to vision-capable models
        vision_models = filter_vision_models(all_models)

        logger.info(f"Retrieved {len(vision_models)} vision models")
        return vision_models

    except Exception as e:
        logger.error(f"Failed to list vision models: {e!s}")
        raise
