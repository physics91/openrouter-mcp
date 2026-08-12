import base64
import io
from unittest.mock import Mock

import pytest
from PIL import Image

from src.openrouter_mcp.handlers import multimodal
from src.openrouter_mcp.handlers.multimodal import (
    _optimize_image_to_limit,
    process_image,
)


class RecordingImage:
    mode = "RGB"
    size = (100, 50)

    def __init__(self, quality_payloads, resize_payloads=None):
        self.quality_payloads = list(quality_payloads)
        self.resize_payloads = list(resize_payloads or [])
        self.save_calls = []
        self.resize_calls = []
        self.resized_save_calls = []

    def save(self, buffer, *, format, quality, optimize):
        self.save_calls.append((format, quality, optimize))
        buffer.write(self.quality_payloads.pop(0))

    def resize(self, size, resampling):
        self.resize_calls.append((size, resampling))
        return RecordingResizedImage(self)


class RecordingResizedImage:
    mode = "RGB"

    def __init__(self, parent):
        self.parent = parent

    def save(self, buffer, *, format, quality, optimize):
        self.parent.resized_save_calls.append((format, quality, optimize))
        buffer.write(self.parent.resize_payloads.pop(0))


def test_optimize_image_preserves_quality_attempt_order_and_early_success():
    image = RecordingImage([b"x" * 11, b"done"])

    optimized = _optimize_image_to_limit(image, "JPEG", max_size_bytes=10)

    assert base64.b64decode(optimized) == b"done"
    assert image.save_calls == [
        ("JPEG", 85, True),
        ("JPEG", 70, True),
    ]
    assert image.resize_calls == []


def test_optimize_image_preserves_resize_order_and_final_fallback():
    image = RecordingImage(
        quality_payloads=[b"x" * 11] * 5,
        resize_payloads=[b"x" * 11] * 6 + [b"final-output"],
    )

    optimized = _optimize_image_to_limit(image, "JPEG", max_size_bytes=10)

    assert base64.b64decode(optimized) == b"final-output"
    assert [quality for _, quality, _ in image.save_calls] == [85, 70, 55, 40, 25]
    assert [size for size, _ in image.resize_calls] == [
        (80, 40),
        (70, 35),
        (60, 30),
        (50, 25),
        (40, 20),
        (30, 15),
        (30, 15),
    ]
    assert [quality for _, quality, _ in image.resized_save_calls] == [
        75,
        75,
        75,
        75,
        75,
        75,
        50,
    ]


def test_optimize_image_converts_unsupported_rgba_format_to_jpeg():
    image = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))

    optimized = _optimize_image_to_limit(image, "BMP", max_size_bytes=100_000)

    with Image.open(io.BytesIO(base64.b64decode(optimized))) as converted:
        assert converted.format == "JPEG"
        assert converted.mode == "RGB"
        assert converted.size == (10, 10)


def test_process_image_rejects_oversized_base64_before_open_or_error_log(monkeypatch):
    monkeypatch.setattr(multimodal.ImageProcessingConfig, "MAX_BASE64_SIZE", 5)
    image_open = Mock()
    error_log = Mock()
    monkeypatch.setattr(multimodal.Image, "open", image_open)
    monkeypatch.setattr(multimodal.logger, "error", error_log)

    with pytest.raises(
        ValueError,
        match="Base64 data too large: 6 bytes exceeds 5 bytes",
    ):
        process_image("abcdef")

    image_open.assert_not_called()
    error_log.assert_not_called()
