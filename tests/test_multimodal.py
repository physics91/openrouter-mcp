import pytest
import base64
import io
import json
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

# Test fixtures
@pytest.fixture
def sample_image_base64():
    """Create a sample base64 encoded image for testing."""
    # Create a simple 100x100 red image
    image = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG')
    image_bytes = buffer.getvalue()
    return base64.b64encode(image_bytes).decode('utf-8')

@pytest.fixture
def sample_large_image_base64():
    """Create a large base64 encoded image for testing resize functionality."""
    # Create a 3000x3000 image to test resizing
    image = Image.new('RGB', (3000, 3000), color='blue')
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG')
    image_bytes = buffer.getvalue()
    return base64.b64encode(image_bytes).decode('utf-8')

@pytest.fixture
def sample_image_url():
    """Sample image URL for testing."""
    return "https://example.com/image.jpg"

@pytest.fixture
def sample_vision_models():
    """Sample list of vision-capable models."""
    return [
        {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"]
            }
        },
        {
            "id": "anthropic/claude-3-sonnet",
            "name": "Claude 3 Sonnet",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"]
            }
        },
        {
            "id": "openai/gpt-3.5-turbo",
            "name": "GPT-3.5 Turbo",
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"]
            }
        }
    ]


class TestImageProcessing:
    """Test image processing utilities."""

    def test_encode_image_to_base64_with_file_path(self, tmp_path):
        """Test encoding image file to base64."""
        from src.openrouter_mcp.handlers.multimodal import encode_image_to_base64
        
        # Create a test image file
        image = Image.new('RGB', (100, 100), color='green')
        image_path = tmp_path / "test_image.jpg"
        image.save(image_path)
        
        # Test encoding
        base64_string = encode_image_to_base64(str(image_path))
        
        # Verify it's a valid base64 string
        assert isinstance(base64_string, str)
        assert len(base64_string) > 0
        # Verify we can decode it back
        decoded_bytes = base64.b64decode(base64_string)
        assert len(decoded_bytes) > 0

    def test_encode_image_to_base64_with_bytes(self):
        """Test encoding image bytes to base64."""
        from src.openrouter_mcp.handlers.multimodal import encode_image_to_base64
        
        # Create image bytes
        image = Image.new('RGB', (100, 100), color='green')
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()
        
        # Test encoding
        base64_string = encode_image_to_base64(image_bytes)
        
        # Verify it's a valid base64 string
        assert isinstance(base64_string, str)
        assert len(base64_string) > 0
        decoded_bytes = base64.b64decode(base64_string)
        assert decoded_bytes == image_bytes

    def test_validate_image_format_valid_formats(self):
        """Test image format validation for supported formats."""
        from src.openrouter_mcp.handlers.multimodal import validate_image_format
        
        valid_formats = ['JPEG', 'PNG', 'WEBP', 'GIF']
        
        for format_name in valid_formats:
            assert validate_image_format(format_name) == True

    def test_validate_image_format_invalid_formats(self):
        """Test image format validation for unsupported formats."""
        from src.openrouter_mcp.handlers.multimodal import validate_image_format
        
        invalid_formats = ['BMP', 'TIFF', 'ICO', 'SVG']
        
        for format_name in invalid_formats:
            assert validate_image_format(format_name) == False

    def test_process_image_no_resize_needed(self, sample_image_base64):
        """Test image processing when no resize is needed."""
        from src.openrouter_mcp.handlers.multimodal import process_image
        
        # Process small image (should not be resized)
        processed_data, was_resized = process_image(sample_image_base64)
        
        assert isinstance(processed_data, str)
        assert was_resized == False
        # Should be the same as input for small images
        assert len(processed_data) == len(sample_image_base64)

    def test_process_image_resize_needed(self, sample_large_image_base64):
        """Test image processing when resize is needed."""
        from src.openrouter_mcp.handlers.multimodal import process_image
        
        # Process large image with very small limit to force resize
        processed_data, was_resized = process_image(sample_large_image_base64, max_size_mb=0.1)
        
        assert isinstance(processed_data, str)
        assert was_resized == True
        # Processed image should be smaller than original
        assert len(processed_data) < len(sample_large_image_base64)

    def test_process_image_max_size_limit(self):
        """Test image processing respects max size limit."""
        from src.openrouter_mcp.handlers.multimodal import process_image
        
        # Create a very large image that exceeds size limits
        image = Image.new('RGB', (5000, 5000), color='red')
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=95)  # High quality = large size
        large_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Process should resize it
        processed_data, was_resized = process_image(large_image_base64)
        
        # Check that the processed image is under the size limit
        processed_bytes = base64.b64decode(processed_data)
        max_size_mb = 20
        assert len(processed_bytes) <= max_size_mb * 1024 * 1024

    def test_format_vision_message_with_base64_image(self, sample_image_base64):
        """Test formatting vision message with base64 image."""
        from src.openrouter_mcp.handlers.multimodal import format_vision_message
        
        message = format_vision_message(
            text="What's in this image?",
            image_data=sample_image_base64,
            image_type="base64"
        )
        
        expected_structure = {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{sample_image_base64}"}
                }
            ]
        }
        
        assert message == expected_structure

    def test_format_vision_message_with_url_image(self, sample_image_url):
        """Test formatting vision message with image URL."""
        from src.openrouter_mcp.handlers.multimodal import format_vision_message
        
        message = format_vision_message(
            text="Describe this image",
            image_data=sample_image_url,
            image_type="url"
        )
        
        expected_structure = {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image"},
                {
                    "type": "image_url",
                    "image_url": {"url": sample_image_url}
                }
            ]
        }
        
        assert message == expected_structure

    def test_format_vision_message_multiple_images(self, sample_image_base64, sample_image_url):
        """Test formatting vision message with multiple images."""
        from src.openrouter_mcp.handlers.multimodal import format_vision_message
        
        # Test with list of images
        images = [
            {"data": sample_image_base64, "type": "base64"},
            {"data": sample_image_url, "type": "url"}
        ]
        
        message = format_vision_message(
            text="Compare these images",
            images=images
        )
        
        # Should have text + 2 image entries
        assert len(message["content"]) == 3
        assert message["content"][0]["type"] == "text"
        assert message["content"][1]["type"] == "image_url"
        assert message["content"][2]["type"] == "image_url"


class TestVisionModelSupport:
    """Test vision model detection and support."""

    def test_is_vision_model_with_vision_capable(self, sample_vision_models):
        """Test vision model detection for models that support images."""
        from src.openrouter_mcp.handlers.multimodal import is_vision_model
        
        vision_model = sample_vision_models[0]  # GPT-4o
        assert is_vision_model(vision_model) == True

    def test_is_vision_model_with_text_only(self, sample_vision_models):
        """Test vision model detection for text-only models."""
        from src.openrouter_mcp.handlers.multimodal import is_vision_model
        
        text_model = sample_vision_models[2]  # GPT-3.5 Turbo
        assert is_vision_model(text_model) == False

    def test_filter_vision_models(self, sample_vision_models):
        """Test filtering models to get only vision-capable ones."""
        from src.openrouter_mcp.handlers.multimodal import filter_vision_models
        
        vision_models = filter_vision_models(sample_vision_models)
        
        assert len(vision_models) == 2
        assert vision_models[0]["id"] == "openai/gpt-4o"
        assert vision_models[1]["id"] == "anthropic/claude-3-sonnet"

    def test_get_vision_model_names(self, sample_vision_models):
        """Test getting names of vision-capable models."""
        from src.openrouter_mcp.handlers.multimodal import get_vision_model_names
        
        model_names = get_vision_model_names(sample_vision_models)
        expected_names = ["GPT-4o", "Claude 3 Sonnet"]
        
        assert model_names == expected_names


class TestMultimodalMCPHandlers:
    """Test MCP handlers for multimodal functionality."""

    def test_chat_with_vision_base64_image(self, sample_image_base64):
        """Test chat with vision using base64 image - validates request structure."""
        from src.openrouter_mcp.handlers.multimodal import VisionChatRequest, ImageInput
        
        # Test that we can create valid request objects
        request = VisionChatRequest(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "What's in this image?"}],
            images=[ImageInput(data=sample_image_base64, type="base64")]
        )
        
        assert request.model == "openai/gpt-4o"
        assert len(request.images) == 1
        assert request.images[0].type == "base64"
        assert request.images[0].data == sample_image_base64

    def test_chat_with_vision_url_image(self, sample_image_url):
        """Test chat with vision using image URL - validates request structure."""
        from src.openrouter_mcp.handlers.multimodal import VisionChatRequest, ImageInput
        
        # Test that we can create valid request objects
        request = VisionChatRequest(
            model="anthropic/claude-3-sonnet",
            messages=[{"role": "user", "content": "Describe this image"}],
            images=[ImageInput(data=sample_image_url, type="url")]
        )
        
        assert request.model == "anthropic/claude-3-sonnet"
        assert len(request.images) == 1
        assert request.images[0].type == "url"
        assert request.images[0].data == sample_image_url

    def test_chat_with_vision_streaming(self, sample_image_base64):
        """Test streaming chat with vision - validates request structure."""
        from src.openrouter_mcp.handlers.multimodal import VisionChatRequest, ImageInput
        
        # Test that we can create valid streaming request objects
        request = VisionChatRequest(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "What's in this image?"}],
            images=[ImageInput(data=sample_image_base64, type="base64")],
            stream=True
        )
        
        assert request.model == "openai/gpt-4o"
        assert request.stream == True
        assert len(request.images) == 1

    def test_list_vision_models(self, sample_vision_models):
        """Test listing vision-capable models - validates filtering logic."""
        from src.openrouter_mcp.handlers.multimodal import filter_vision_models, VisionModelRequest
        
        # Test the filtering function directly
        vision_models = filter_vision_models(sample_vision_models)
        
        # Should return only vision-capable models
        assert len(vision_models) == 2
        assert vision_models[0]["id"] == "openai/gpt-4o"
        assert vision_models[1]["id"] == "anthropic/claude-3-sonnet"

    def test_list_vision_models_with_filter(self, sample_vision_models):
        """Test listing vision models with name filter - validates filter logic."""
        from src.openrouter_mcp.handlers.multimodal import filter_vision_models, VisionModelRequest
        
        # Test the filtering function directly with name filter
        vision_models = filter_vision_models(sample_vision_models)
        gpt_models = [model for model in vision_models if "gpt" in model["id"].lower()]
        
        # Should return only GPT vision models
        assert len(gpt_models) == 1
        assert gpt_models[0]["id"] == "openai/gpt-4o"

    def test_vision_chat_request_validation(self):
        """Test VisionChatRequest Pydantic model validation."""
        from src.openrouter_mcp.handlers.multimodal import VisionChatRequest, ImageInput
        
        # Valid request
        valid_request = VisionChatRequest(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "Test"}],
            images=[ImageInput(data="test_image.jpg", type="base64")]
        )
        
        assert valid_request.model == "openai/gpt-4o"
        assert len(valid_request.messages) == 1
        assert len(valid_request.images) == 1
        assert valid_request.temperature == 0.7  # Default value

    def test_image_input_validation(self):
        """Test ImageInput Pydantic model validation."""
        from src.openrouter_mcp.handlers.multimodal import ImageInput
        
        # Valid base64 input
        base64_input = ImageInput(data="base64_string_here", type="base64")
        assert base64_input.type == "base64"
        
        # Valid URL input
        url_input = ImageInput(data="https://example.com/image.jpg", type="url")
        assert url_input.type == "url"
        
        # Invalid type should raise validation error
        with pytest.raises(ValueError):
            ImageInput(data="test", type="invalid_type")


class TestClientIntegration:
    """Test integration with OpenRouter client for vision functionality."""

    @pytest.mark.asyncio
    async def test_openrouter_client_vision_method_exists(self):
        """Test that OpenRouter client has vision methods."""
        from src.openrouter_mcp.client.openrouter import OpenRouterClient
        
        # Check if the methods exist (will be implemented in GREEN phase)
        client = OpenRouterClient(api_key="test")
        
        assert hasattr(client, 'chat_completion_with_vision')
        assert hasattr(client, 'stream_chat_completion_with_vision')

    @pytest.mark.asyncio 
    async def test_client_vision_methods_callable(self):
        """Test that vision methods are callable."""
        from src.openrouter_mcp.client.openrouter import OpenRouterClient
        
        client = OpenRouterClient(api_key="test")
        
        # Methods should be callable (even if not implemented yet)
        assert callable(getattr(client, 'chat_completion_with_vision', None))
        assert callable(getattr(client, 'stream_chat_completion_with_vision', None))