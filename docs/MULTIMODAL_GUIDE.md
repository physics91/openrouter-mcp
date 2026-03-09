# Multimodal/Vision Guide

This guide describes the current vision workflow supported by the OpenRouter MCP server.

## Overview

The server exposes two vision tools:

- `chat_with_vision`
- `list_vision_models`

Vision requests accept images in exactly two formats:

- `type: "base64"`
- `type: "url"`

File path input is intentionally unsupported for security reasons.

## List Vision Models

Use `list_vision_models` to inspect the vision-capable model set available through OpenRouter.

```json
{
  "name": "list_vision_models"
}
```

## Basic Image Analysis

```json
{
  "name": "chat_with_vision",
  "arguments": {
    "request": {
      "model": "openai/gpt-4o",
      "messages": [
        {"role": "user", "content": "What do you see in this image?"}
      ],
      "images": [
        {
          "data": "https://example.com/image.jpg",
          "type": "url"
        }
      ]
    }
  }
}
```

## Supported Image Sources

### URLs

```json
{
  "images": [
    {"data": "https://example.com/image.jpg", "type": "url"}
  ]
}
```

### Base64 Data

```json
{
  "images": [
    {
      "data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABA...",
      "type": "base64"
    }
  ]
}
```

## Converting Local Files Safely

If your image starts as a local file, read it yourself and send base64 bytes to the tool.

```python
from openrouter_mcp.handlers.multimodal import ImageInput, encode_image_to_base64

with open("diagram.png", "rb") as image_file:
    image_bytes = image_file.read()

image = ImageInput(
    data=encode_image_to_base64(image_bytes),
    type="base64",
)
```

## Multiple Images

```json
{
  "name": "chat_with_vision",
  "arguments": {
    "request": {
      "model": "anthropic/claude-3-opus",
      "messages": [
        {"role": "user", "content": "Compare these images and describe the differences."}
      ],
      "images": [
        {"data": "https://example.com/image-a.png", "type": "url"},
        {"data": "https://example.com/image-b.png", "type": "url"}
      ]
    }
  }
}
```

## Processing Notes

- Supported formats: JPEG, PNG, GIF, WebP
- Large images may be resized automatically to stay within API-safe limits
- Vision support depends on the target model returned by `list_vision_models`

## Troubleshooting

### Invalid Input Type

If you send `type: "path"` the request will fail validation. Convert the file to base64 first or upload it somewhere reachable by URL.

### URL Fetch Failures

- Confirm the URL is directly reachable by the server
- Avoid URLs behind authentication unless you are using a presigned link
- Prefer short-lived presigned URLs for private assets

### Image Too Large

- The server will attempt safe resizing automatically
- If the image still fails, reduce resolution before encoding it

### Unsupported Model

- Call `list_vision_models` and switch to a currently vision-capable model

## Best Practices

- Use base64 when the image is local or generated on the fly
- Use direct or presigned URLs when the image is already hosted
- Keep prompts explicit about extraction, comparison, OCR, or classification goals
- Prefer cropped images for charts, documents, and screenshots

## Related Documents

- `docs/API.md`
- `docs/TROUBLESHOOTING.md`
- `docs/SECURITY.md`
