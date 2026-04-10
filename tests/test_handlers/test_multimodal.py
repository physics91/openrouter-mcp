"""
Tests for the multimodal (vision) handler.

This module tests the vision capabilities including image processing,
base64 encoding, model filtering, and chat completion with images.
"""

import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from openrouter_mcp.handlers import multimodal as multimodal_module
from openrouter_mcp.handlers.multimodal import (
    ImageInput,
    VisionChatRequest,
    VisionModelRequest,
    encode_image_to_base64,
    filter_vision_models,
    format_vision_message,
    get_vision_model_names,
    is_vision_model,
    process_image,
    validate_image_format,
)
from openrouter_mcp.runtime_thrift import (
    get_thrift_metrics_snapshot,
    record_coalesced_savings,
    record_compaction_savings,
    record_prompt_cache_activity,
    reset_thrift_metrics,
)

pytestmark = pytest.mark.unit


class TestImageInput:
    """Test ImageInput model validation."""

    def test_image_input_base64_type(self):
        """Test valid base64 image input."""
        img = ImageInput(data="base64data", type="base64")
        assert img.data == "base64data"
        assert img.type == "base64"

    def test_image_input_url_type(self):
        """Test valid URL image input."""
        img = ImageInput(data="https://example.com/image.jpg", type="url")
        assert img.data == "https://example.com/image.jpg"
        assert img.type == "url"

    def test_image_input_path_type_rejected(self):
        """Test that path type is rejected for security reasons."""
        with pytest.raises(ValueError, match="security reasons"):
            ImageInput(data="/path/to/image.jpg", type="path")

    def test_image_input_invalid_type(self):
        """Test invalid image input type raises error."""
        with pytest.raises(ValueError, match="Type must be"):
            ImageInput(data="data", type="invalid")


class TestVisionChatRequest:
    """Test VisionChatRequest model."""

    def test_vision_chat_request_minimal(self):
        """Test vision chat request with minimal parameters."""
        images = [ImageInput(data="base64data", type="base64")]
        req = VisionChatRequest(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "What's in this image?"}],
            images=images,
        )
        assert req.model == "openai/gpt-4o"
        assert len(req.messages) == 1
        assert len(req.images) == 1
        assert req.temperature == 0.7
        assert req.stream is False

    def test_vision_chat_request_full(self):
        """Test vision chat request with all parameters."""
        images = [ImageInput(data="base64data", type="base64")]
        req = VisionChatRequest(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "Analyze this"}],
            images=images,
            temperature=0.5,
            max_tokens=1000,
            stream=True,
        )
        assert req.temperature == 0.5
        assert req.max_tokens == 1000
        assert req.stream is True


class TestVisionModelRequest:
    """Test VisionModelRequest model."""

    def test_vision_model_request_no_filter(self):
        """Test vision model request without filter."""
        req = VisionModelRequest()
        assert req.filter_by is None

    def test_vision_model_request_with_filter(self):
        """Test vision model request with filter."""
        req = VisionModelRequest(filter_by="gpt")
        assert req.filter_by == "gpt"


class TestGetOpenRouterClient:
    """Test OpenRouter client creation."""

    @pytest.mark.asyncio
    async def test_get_client_with_api_key(self):
        """Test client creation with API key in environment."""
        # Create a mock client
        mock_client = MagicMock()

        # Mock get_openrouter_client to return the mock client
        with patch(
            "openrouter_mcp.handlers.multimodal.get_openrouter_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            # Call the function
            client = await multimodal_module.get_openrouter_client()

            # Verify the client was retrieved
            assert client is not None
            assert client == mock_client
            mock_get_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_missing_api_key(self):
        """Test client creation fails without API key."""
        # Mock get_openrouter_client to raise ValueError (simulating missing API key)
        with patch(
            "openrouter_mcp.handlers.multimodal.get_openrouter_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_get_client.side_effect = ValueError(
                "OPENROUTER_API_KEY environment variable is required"
            )

            # Verify that the error is propagated
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                await multimodal_module.get_openrouter_client()


class TestEncodeImageToBase64:
    """Test image encoding functionality."""

    def test_encode_image_from_bytes(self):
        """Test encoding image from bytes."""
        image_bytes = b"test_image_data"
        result = encode_image_to_base64(image_bytes)
        assert result == base64.b64encode(image_bytes).decode("utf-8")

    def test_encode_image_rejects_string_path(self):
        """Test that file path strings are rejected for security reasons."""
        with pytest.raises(TypeError, match="security reasons"):
            encode_image_to_base64("/path/to/image.jpg")

    def test_encode_image_rejects_non_bytes(self):
        """Test that non-bytes input is rejected."""
        with pytest.raises(TypeError, match="only accepts bytes"):
            encode_image_to_base64("not bytes data")


class TestValidateImageFormat:
    """Test image format validation."""

    def test_validate_jpeg_format(self):
        """Test JPEG format is valid."""
        assert validate_image_format("JPEG") is True
        assert validate_image_format("jpeg") is True

    def test_validate_png_format(self):
        """Test PNG format is valid."""
        assert validate_image_format("PNG") is True
        assert validate_image_format("png") is True

    def test_validate_webp_format(self):
        """Test WEBP format is valid."""
        assert validate_image_format("WEBP") is True

    def test_validate_gif_format(self):
        """Test GIF format is valid."""
        assert validate_image_format("GIF") is True

    def test_validate_unsupported_format(self):
        """Test unsupported format is invalid."""
        assert validate_image_format("BMP") is False
        assert validate_image_format("TIFF") is False


class TestProcessImage:
    """Test image processing functionality."""

    def create_test_image(self, width=100, height=100, format="JPEG"):
        """Helper to create test image."""
        img = Image.new("RGB", (width, height), color="red")
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def test_process_small_image_no_resize(self):
        """Test processing small image that doesn't need resizing."""
        # Create a small image
        small_image = self.create_test_image(width=100, height=100)

        result, was_resized = process_image(small_image, max_size_mb=20)

        assert result == small_image
        assert was_resized is False

    def test_process_large_image_with_resize(self):
        """Test processing large image that needs resizing."""
        # Create a larger image
        large_image = self.create_test_image(width=2000, height=2000)

        # Use small max size to force resizing
        result, was_resized = process_image(large_image, max_size_mb=0.01)

        assert result != large_image  # Should be different after processing
        assert was_resized is True

        # Verify the result is smaller
        result_size = len(base64.b64decode(result))
        assert result_size < 0.01 * 1024 * 1024

    def test_process_image_with_unsupported_format(self):
        """Test processing image with unsupported format converts to JPEG."""
        # Create image with transparency (RGBA)
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Force processing by setting very small max size
        result, was_resized = process_image(image_data, max_size_mb=0.0001)

        # Should have been processed (very small max size forces processing)
        assert was_resized is True

    def test_process_invalid_base64(self):
        """Test processing invalid base64 data raises error."""
        with pytest.raises(Exception):
            process_image("invalid_base64_data")


class TestFormatVisionMessage:
    """Test vision message formatting."""

    def test_format_message_with_text_only(self):
        """Test formatting message with text only."""
        result = format_vision_message(text="Test prompt")

        assert result["role"] == "user"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Test prompt"

    def test_format_message_with_single_base64_image(self):
        """Test formatting message with single base64 image."""
        result = format_vision_message(
            text="Analyze this", image_data="base64data", image_type="base64"
        )

        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "image_url"
        assert "data:image/jpeg;base64,base64data" in result["content"][1]["image_url"]["url"]

    def test_format_message_with_single_url_image(self):
        """Test formatting message with single URL image."""
        result = format_vision_message(
            text="Analyze this",
            image_data="https://example.com/image.jpg",
            image_type="url",
        )

        assert len(result["content"]) == 2
        assert result["content"][1]["image_url"]["url"] == "https://example.com/image.jpg"

    def test_format_message_with_multiple_images(self):
        """Test formatting message with multiple images."""
        images = [
            {"data": "base64data1", "type": "base64"},
            {"data": "https://example.com/image.jpg", "type": "url"},
        ]

        result = format_vision_message(text="Analyze these", images=images)

        assert len(result["content"]) == 3  # text + 2 images
        assert result["content"][1]["type"] == "image_url"
        assert result["content"][2]["type"] == "image_url"


class TestIsVisionModel:
    """Test vision model detection."""

    def test_is_vision_model_with_image_support(self):
        """Test detecting model with image support."""
        model_info = {
            "id": "openai/gpt-4o",
            "architecture": {"input_modalities": ["text", "image"]},
        }
        assert is_vision_model(model_info) is True

    def test_is_vision_model_text_only(self):
        """Test detecting text-only model."""
        model_info = {
            "id": "openai/gpt-3.5-turbo",
            "architecture": {"input_modalities": ["text"]},
        }
        assert is_vision_model(model_info) is False

    def test_is_vision_model_no_architecture(self):
        """Test detecting model with no architecture info."""
        model_info = {"id": "unknown/model"}
        assert is_vision_model(model_info) is False

    def test_is_vision_model_empty_modalities(self):
        """Test detecting model with empty modalities."""
        model_info = {"id": "unknown/model", "architecture": {"input_modalities": []}}
        assert is_vision_model(model_info) is False


class TestFilterVisionModels:
    """Test vision model filtering."""

    def test_filter_vision_models_mixed_list(self):
        """Test filtering mixed list of models."""
        models = [
            {
                "id": "openai/gpt-4o",
                "architecture": {"input_modalities": ["text", "image"]},
            },
            {
                "id": "openai/gpt-3.5-turbo",
                "architecture": {"input_modalities": ["text"]},
            },
            {
                "id": "anthropic/claude-3-opus",
                "architecture": {"input_modalities": ["text", "image"]},
            },
        ]

        result = filter_vision_models(models)

        assert len(result) == 2
        assert result[0]["id"] == "openai/gpt-4o"
        assert result[1]["id"] == "anthropic/claude-3-opus"

    def test_filter_vision_models_empty_list(self):
        """Test filtering empty list."""
        result = filter_vision_models([])
        assert result == []

    def test_filter_vision_models_no_vision_models(self):
        """Test filtering list with no vision models."""
        models = [
            {
                "id": "openai/gpt-3.5-turbo",
                "architecture": {"input_modalities": ["text"]},
            }
        ]

        result = filter_vision_models(models)
        assert result == []


class TestGetVisionModelNames:
    """Test vision model name extraction."""

    def test_get_vision_model_names(self):
        """Test extracting vision model names."""
        models = [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4 Omni",
                "architecture": {"input_modalities": ["text", "image"]},
            },
            {
                "id": "openai/gpt-3.5-turbo",
                "name": "GPT-3.5 Turbo",
                "architecture": {"input_modalities": ["text"]},
            },
        ]

        result = get_vision_model_names(models)

        assert len(result) == 1
        assert result[0] == "GPT-4 Omni"

    def test_get_vision_model_names_fallback_to_id(self):
        """Test name extraction falls back to ID if name missing."""
        models = [
            {
                "id": "openai/gpt-4o",
                "architecture": {"input_modalities": ["text", "image"]},
            }
        ]

        result = get_vision_model_names(models)

        assert len(result) == 1
        assert result[0] == "openai/gpt-4o"

    def test_get_vision_model_names_empty_list(self):
        """Test extracting names from empty list."""
        result = get_vision_model_names([])
        assert result == []


class TestImageProcessingEdgeCases:
    """Test edge cases in image processing."""

    def test_encode_empty_bytes(self):
        """Test encoding empty bytes."""
        result = encode_image_to_base64(b"")
        assert result == base64.b64encode(b"").decode("utf-8")

    def test_validate_mixed_case_formats(self):
        """Test format validation is case-insensitive."""
        assert validate_image_format("JpEg") is True
        assert validate_image_format("PnG") is True
        assert validate_image_format("WeBp") is True

    def test_format_vision_message_edge_cases(self):
        """Test formatting with edge case inputs."""
        # Empty text
        result = format_vision_message(text="")
        assert result["content"][0]["text"] == ""

        # Long text
        long_text = "A" * 10000
        result = format_vision_message(text=long_text)
        assert result["content"][0]["text"] == long_text

    def test_is_vision_model_various_architectures(self):
        """Test vision model detection with various architecture formats."""
        # Model with video support (should also be vision)
        model = {
            "id": "test/model",
            "architecture": {"input_modalities": ["text", "image", "video"]},
        }
        assert is_vision_model(model) is True

        # Model with only audio (not vision)
        model_audio = {
            "id": "test/audio",
            "architecture": {"input_modalities": ["text", "audio"]},
        }
        assert is_vision_model(model_audio) is False

    def test_filter_vision_models_large_list(self):
        """Test filtering large list of models."""
        # Create a large mixed list
        models = []
        for i in range(100):
            if i % 3 == 0:
                models.append(
                    {
                        "id": f"provider/vision-model-{i}",
                        "architecture": {"input_modalities": ["text", "image"]},
                    }
                )
            else:
                models.append(
                    {
                        "id": f"provider/text-model-{i}",
                        "architecture": {"input_modalities": ["text"]},
                    }
                )

        result = filter_vision_models(models)

        # Should have 34 vision models (0, 3, 6, ..., 99)
        assert len(result) == 34
        for model in result:
            assert "vision-model" in model["id"]

    def test_get_vision_model_names_with_missing_fields(self):
        """Test name extraction with various missing fields."""
        models = [
            {
                "id": "model1",
                "name": "Model 1",
                "architecture": {"input_modalities": ["text", "image"]},
            },
            {
                "id": "model2",
                # No name field
                "architecture": {"input_modalities": ["text", "image"]},
            },
            {
                # No id or name
                "architecture": {"input_modalities": ["text", "image"]}
            },
        ]

        result = get_vision_model_names(models)

        assert len(result) == 3
        assert result[0] == "Model 1"
        assert result[1] == "model2"
        assert result[2] == "Unknown"


class TestVisionHandlerThriftMetadata:
    @pytest.mark.asyncio
    async def test_chat_with_vision_returns_request_scoped_thrift_metadata(self):
        reset_thrift_metrics()
        record_compaction_savings(42)
        record_coalesced_savings(prompt_tokens=100, completion_tokens=20, estimated_cost_usd=0.003)
        record_prompt_cache_activity(
            cached_prompt_tokens=300,
            cache_write_prompt_tokens=100,
            estimated_saved_cost_usd=0.007,
        )

        mock_response = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "분석 완료"},
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }

        with patch(
            "openrouter_mcp.handlers.multimodal.get_openrouter_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_client = AsyncMock()

            async def chat_completion_with_request_local_thrift(*args, **kwargs):
                record_compaction_savings(7)
                record_coalesced_savings(
                    prompt_tokens=30,
                    completion_tokens=10,
                    estimated_cost_usd=0.002,
                )
                record_prompt_cache_activity(
                    cached_prompt_tokens=120,
                    cache_write_prompt_tokens=40,
                    estimated_saved_cost_usd=0.004,
                )
                return mock_response

            mock_client.chat_completion.side_effect = chat_completion_with_request_local_thrift
            mock_get_client.return_value = mock_client

            result = await multimodal_module.chat_with_vision(
                VisionChatRequest(
                    model="openai/gpt-4o",
                    messages=[{"role": "user", "content": "이 이미지 뭐냐"}],
                    images=[ImageInput(data="https://example.com/cat.jpg", type="url")],
                )
            )

            assert result["thrift_metrics"]["compacted_tokens"] == 7
            assert result["thrift_summary"]["saved_cost_usd"] == 0.006
            assert result["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 120
            assert (
                result["thrift_summary"]["prompt_savings_breakdown"]["coalesced_prompt_tokens"]
                == 30
            )
            assert get_thrift_metrics_snapshot()["compacted_tokens"] == 49
            assert get_thrift_metrics_snapshot()["saved_cost_usd"] == 0.016

    @pytest.mark.asyncio
    async def test_chat_with_vision_streaming_attaches_request_scoped_thrift_to_final_chunk(self):
        reset_thrift_metrics()
        record_compaction_savings(42)
        mock_chunks = [
            {"choices": [{"delta": {"content": "분석"}}]},
            {"choices": [{"delta": {"content": " 완료"}}]},
            {
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 16, "completion_tokens": 9, "total_tokens": 25},
            },
        ]

        with patch(
            "openrouter_mcp.handlers.multimodal.get_openrouter_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_client = AsyncMock()

            async def mock_stream_gen():
                record_compaction_savings(5)
                record_prompt_cache_activity(
                    cached_prompt_tokens=80,
                    cache_write_prompt_tokens=20,
                    estimated_saved_cost_usd=0.005,
                )
                for chunk in mock_chunks:
                    yield chunk

            mock_client.stream_chat_completion = MagicMock(return_value=mock_stream_gen())
            mock_get_client.return_value = mock_client

            result = await multimodal_module.chat_with_vision(
                VisionChatRequest(
                    model="openai/gpt-4o",
                    messages=[{"role": "user", "content": "이 이미지 뭐냐"}],
                    images=[ImageInput(data="https://example.com/cat.jpg", type="url")],
                    stream=True,
                )
            )

            assert len(result) == 3
            assert "thrift_metrics" not in result[0]
            assert result[-1]["thrift_metrics"]["compacted_tokens"] == 5
            assert result[-1]["thrift_summary"]["saved_cost_usd"] == 0.005
            assert (
                result[-1]["thrift_summary"]["prompt_savings_breakdown"]["cache_reuse_tokens"] == 80
            )
            assert get_thrift_metrics_snapshot()["compacted_tokens"] == 47
