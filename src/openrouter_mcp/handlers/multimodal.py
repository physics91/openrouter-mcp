import base64
import io
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image
from pydantic import BaseModel, Field, field_validator

from ..config.constants import ImageProcessingConfig

# Import shared MCP instance and client manager from registry
from ..mcp_registry import get_openrouter_client, mcp

# Import centralized request base classes
from ..models.requests import BaseChatRequest
from ..utils.async_utils import collect_async_iterable
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
    def validate_type(cls, v):
        if v not in ["base64", "url"]:
            raise ValueError(
                "Type must be 'base64' or 'url'. File path access is not supported for security reasons."
            )
        return v


class VisionChatRequest(BaseChatRequest):
    """Request for chat completion with vision."""

    images: List[ImageInput] = Field(..., description="List of images to analyze")


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
        logger.error(f"Failed to encode image to base64: {str(e)}")
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


def process_image(
    base64_data: str, max_size_mb: int = ImageProcessingConfig.MAX_SIZE_MB
) -> Tuple[str, bool]:
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

        # Security: Check decoded size before PIL processing
        safe_limit = max(max_size_bytes * 5, 1024 * 1024)  # At least 1MB headroom
        if len(image_bytes) > safe_limit:
            raise ValueError(
                f"Decoded image too large: {len(image_bytes)} bytes exceeds safe limit"
            )

        # If image is already small enough, still validate it
        # Open and validate the image BEFORE returning it
        image = Image.open(io.BytesIO(image_bytes))

        # Security: Validate image dimensions to prevent pixel bombs
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

        # Security: Validate image format before processing
        original_format = image.format
        if not original_format:
            # Try to detect format from image mode and data
            original_format = "JPEG"
            logger.warning("Image format not detected, defaulting to JPEG")

        # If image is already small enough, return early
        if len(image_bytes) <= max_size_bytes:
            return base64_data, False

        # Validate format
        if not validate_image_format(original_format):
            logger.info(f"Converting unsupported format {original_format} to JPEG")
            # Convert unsupported formats to JPEG
            if image.mode in ("RGBA", "LA", "P"):
                # Convert to RGB for JPEG
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(
                    image,
                    mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None,
                )
                image = background
            original_format = "JPEG"

        # Calculate resize ratio to stay under size limit
        # Start with quality reduction
        quality = 85
        while quality > 20:
            buffer = io.BytesIO()
            image.save(buffer, format=original_format, quality=quality, optimize=True)

            if len(buffer.getvalue()) <= max_size_bytes:
                processed_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                return processed_base64, True

            quality -= 15

        # If quality reduction isn't enough, resize image
        width, height = image.size
        resize_ratio = 0.8

        while resize_ratio > 0.3:
            new_width = int(width * resize_ratio)
            new_height = int(height * resize_ratio)

            resized_image = image.resize(
                (new_width, new_height), Image.Resampling.LANCZOS
            )

            buffer = io.BytesIO()
            resized_image.save(
                buffer, format=original_format, quality=75, optimize=True
            )

            if len(buffer.getvalue()) <= max_size_bytes:
                processed_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                return processed_base64, True

            resize_ratio -= 0.1

        # If still too large, use the smallest version
        buffer = io.BytesIO()
        resized_image = image.resize(
            (int(width * 0.3), int(height * 0.3)), Image.Resampling.LANCZOS
        )
        resized_image.save(buffer, format=original_format, quality=50, optimize=True)
        processed_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return processed_base64, True

    except Exception as e:
        logger.error(f"Failed to process image: {str(e)}")
        raise


def format_vision_message(
    text: str,
    image_data: Optional[str] = None,
    image_type: Optional[str] = None,
    images: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
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
    content = [{"type": "text", "text": text}]

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


def is_vision_model(model_info: Dict[str, Any]) -> bool:
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


def filter_vision_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter a list of models to return only vision-capable ones.

    Args:
        models: List of model information dictionaries

    Returns:
        List of vision-capable models
    """
    return [model for model in models if is_vision_model(model)]


def get_vision_model_names(models: List[Dict[str, Any]]) -> List[str]:
    """
    Get names of vision-capable models.

    Args:
        models: List of model information dictionaries

    Returns:
        List of vision model names
    """
    vision_models = filter_vision_models(models)
    return [model.get("name", model.get("id", "Unknown")) for model in vision_models]


@mcp.tool()
async def chat_with_vision(
    request: VisionChatRequest,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
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

    # Get shared client (already in async context, no need for 'async with')
    client = await get_openrouter_client()

    try:
        # Process images and create vision messages
        base_messages = serialize_messages(request.messages)
        vision_messages = []

        for i, message_payload in enumerate(base_messages):
            if i == len(base_messages) - 1:  # Last message, add images
                # Process images
                processed_images = []
                for img in request.images:
                    if img.type == "base64":
                        # Process the image (resize if needed)
                        processed_data, was_resized = process_image(img.data)
                        if was_resized:
                            logger.info("Image was resized for API optimization")
                        processed_images.append(
                            {"data": processed_data, "type": "base64"}
                        )
                    else:
                        processed_images.append({"data": img.data, "type": "url"})

                # Format vision message
                vision_message = format_vision_message(
                    text=message_payload["content"], images=processed_images
                )
                vision_messages.append(vision_message)
            else:
                vision_messages.append(message_payload)

        if request.stream:
            logger.info("Initiating streaming vision chat completion")
            chunks = await collect_async_iterable(
                client.stream_chat_completion(
                    model=request.model,
                    messages=vision_messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
            )

            logger.info(f"Streaming completed with {len(chunks)} chunks")
            return chunks
        else:
            logger.info("Initiating non-streaming vision chat completion")
            response = await client.chat_completion(
                model=request.model,
                messages=vision_messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            logger.info("Vision chat completion successful")
            return response

    except Exception as e:
        logger.error(f"Vision chat completion failed: {str(e)}")
        raise


@mcp.tool()
async def list_vision_models(request: VisionModelRequest) -> List[Dict[str, Any]]:
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
        logger.error(f"Failed to list vision models: {str(e)}")
        raise
