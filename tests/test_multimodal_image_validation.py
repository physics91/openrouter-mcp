from unittest.mock import MagicMock, patch

import pytest

from src.openrouter_mcp.handlers import multimodal

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("max_size_bytes", "decoded_size"),
    [
        (1, 1024 * 1024 + 1),
        (300_000, 1_500_001),
    ],
)
def test_open_validated_image_rejects_decoded_size_before_pil(
    max_size_bytes,
    decoded_size,
):
    image_open = MagicMock()

    with patch.object(multimodal.Image, "open", image_open):
        with pytest.raises(ValueError):
            multimodal._open_validated_image(
                b"x" * decoded_size,
                max_size_bytes,
            )

    image_open.assert_not_called()


def test_open_validated_image_checks_pixel_limit_before_dimension_limit(monkeypatch):
    image = MagicMock(size=(11, 11), format="PNG")
    monkeypatch.setattr(multimodal.ImageProcessingConfig, "MAX_PIXELS", 100)
    monkeypatch.setattr(multimodal.ImageProcessingConfig, "MAX_DIMENSION", 10)

    with patch.object(multimodal.Image, "open", return_value=image):
        with pytest.raises(ValueError, match="Image dimensions too large"):
            multimodal._open_validated_image(b"image", max_size_bytes=100)


def test_open_validated_image_defaults_missing_format_after_dimension_checks():
    image = MagicMock(size=(10, 20), format=None)

    with patch.object(
        multimodal.Image,
        "open",
        return_value=image,
    ), patch.object(multimodal.logger, "warning") as warning:
        result_image, result_format = multimodal._open_validated_image(
            b"image",
            max_size_bytes=100,
        )

    assert result_image is image
    assert result_format == "JPEG"
    warning.assert_called_once()


def test_process_image_delegates_validation_before_small_image_return():
    base64_data = "encoded"
    image_bytes = b"decoded"
    image = MagicMock()

    with patch.object(
        multimodal.base64,
        "b64decode",
        return_value=image_bytes,
    ), patch.object(
        multimodal,
        "_open_validated_image",
        return_value=(image, "PNG"),
    ) as validate, patch.object(
        multimodal, "_optimize_image_to_limit"
    ) as optimize:
        result = multimodal.process_image(base64_data, max_size_mb=1)

    assert result == (base64_data, False)
    validate.assert_called_once_with(image_bytes, 1024 * 1024)
    optimize.assert_not_called()


def test_process_image_passes_validated_image_to_optimizer():
    image_bytes = b"decoded"
    image = MagicMock()

    with patch.object(
        multimodal.base64,
        "b64decode",
        return_value=image_bytes,
    ), patch.object(
        multimodal,
        "_open_validated_image",
        return_value=(image, "WEBP"),
    ) as validate, patch.object(
        multimodal,
        "_optimize_image_to_limit",
        return_value="optimized",
    ) as optimize:
        result = multimodal.process_image("encoded", max_size_mb=0)

    assert result == ("optimized", True)
    validate.assert_called_once_with(image_bytes, 0)
    optimize.assert_called_once_with(image, "WEBP", 0)
