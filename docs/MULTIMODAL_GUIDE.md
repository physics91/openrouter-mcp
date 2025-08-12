# Multimodal/Vision Guide

This guide explains how to use the multimodal (vision) capabilities of the OpenRouter MCP Server to analyze images with AI models.

## Overview

The OpenRouter MCP Server supports vision-capable AI models that can analyze and understand images. This includes:

- **GPT-4 Vision models** (OpenAI)
- **Claude 3 models** with vision (Anthropic)
- **Gemini Pro Vision** (Google)
- **Llama Vision models** (Meta)

## Getting Started

### Prerequisites

Make sure you have the Pillow dependency installed for image processing:

```bash
pip install Pillow>=10.0.0
```

This is already included in `requirements.txt` if you installed the server normally.

### Available Vision Models

Use the `list_vision_models` MCP tool to get current vision-capable models:

```json
{
  "name": "list_vision_models"
}
```

Popular vision models include:
- `openai/gpt-4o` - OpenAI's latest multimodal model
- `openai/gpt-4o-mini` - Fast and cost-effective vision model
- `anthropic/claude-3-opus` - Most capable Claude vision model
- `anthropic/claude-3-sonnet` - Balanced Claude vision model
- `google/gemini-pro-vision` - Google's multimodal AI
- `meta-llama/llama-3.2-90b-vision-instruct` - Meta's vision-capable model

## Using Vision Capabilities

### Basic Image Analysis

Use the `chat_with_vision` MCP tool to analyze images:

```json
{
  "name": "chat_with_vision",
  "arguments": {
    "model": "openai/gpt-4o",
    "messages": [
      {"role": "user", "content": "What do you see in this image?"}
    ],
    "images": [
      {"data": "/path/to/image.jpg", "type": "path"}
    ]
  }
}
```

### Supported Image Sources

The server supports multiple image input formats:

#### 1. File Paths
```json
{
  "images": [
    {"data": "/home/user/photo.jpg", "type": "path"},
    {"data": "./relative/path/image.png", "type": "path"}
  ]
}
```

#### 2. URLs
```json
{
  "images": [
    {"data": "https://example.com/image.jpg", "type": "url"}
  ]
}
```

#### 3. Base64 Data
```json
{
  "images": [
    {"data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABA...", "type": "base64"},
    {"data": "/9j/4AAQSkZJRgABA...", "type": "base64"}
  ]
}
```

### Multiple Images

Analyze multiple images in a single request:

```json
{
  "name": "chat_with_vision",
  "arguments": {
    "model": "openai/gpt-4o",
    "messages": [
      {"role": "user", "content": "Compare these two images and describe the differences"}
    ],
    "images": [
      {"data": "/path/to/image1.jpg", "type": "path"},
      {"data": "https://example.com/image2.png", "type": "url"}
    ]
  }
}
```

### Advanced Parameters

Control the response with additional parameters:

```json
{
  "name": "chat_with_vision",
  "arguments": {
    "model": "anthropic/claude-3-opus",
    "messages": [
      {"role": "user", "content": "Analyze this medical chart for trends"}
    ],
    "images": [
      {"data": "/path/to/chart.png", "type": "path"}
    ],
    "temperature": 0.3,
    "max_tokens": 1000
  }
}
```

## Image Processing Features

### Automatic Resizing

Images are automatically resized if they exceed API limits (typically 20MB):
- Large images are resized while maintaining aspect ratio
- Quality is optimized for API transmission
- The server will log when resizing occurs

### Format Support

Supported image formats:
- **JPEG** (.jpg, .jpeg)
- **PNG** (.png)
- **GIF** (.gif)
- **WebP** (.webp)

### Error Handling

The server provides detailed error messages for:
- Invalid image formats
- Corrupted image data
- Network errors when fetching URLs
- File not found errors

## Use Cases

### Document Analysis
```json
{
  "name": "chat_with_vision",
  "arguments": {
    "model": "openai/gpt-4o",
    "messages": [
      {"role": "user", "content": "Extract all text from this document and format it as markdown"}
    ],
    "images": [
      {"data": "/path/to/document.png", "type": "path"}
    ]
  }
}
```

### Chart and Graph Analysis
```json
{
  "name": "chat_with_vision",
  "arguments": {
    "model": "claude-3-opus",
    "messages": [
      {"role": "user", "content": "Analyze this sales chart and summarize the key trends"}
    ],
    "images": [
      {"data": "https://company.com/sales-chart.png", "type": "url"}
    ]
  }
}
```

### Code Screenshot Analysis
```json
{
  "name": "chat_with_vision",
  "arguments": {
    "model": "openai/gpt-4o",
    "messages": [
      {"role": "user", "content": "Review this code screenshot for bugs and suggest improvements"}
    ],
    "images": [
      {"data": "/path/to/code-screenshot.png", "type": "path"}
    ]
  }
}
```

### Creative Content Analysis
```json
{
  "name": "chat_with_vision",
  "arguments": {
    "model": "anthropic/claude-3-sonnet",
    "messages": [
      {"role": "user", "content": "Describe the artistic style and composition of this painting"}
    ],
    "images": [
      {"data": "https://museum.com/painting.jpg", "type": "url"}
    ]
  }
}
```

## Best Practices

### Model Selection
- **GPT-4o**: Best for general image analysis and document processing
- **GPT-4o-mini**: Fast and cost-effective for simple image tasks
- **Claude 3 Opus**: Excellent for detailed analysis and creative interpretation
- **Claude 3 Sonnet**: Good balance of capability and speed
- **Gemini Pro Vision**: Strong for multimodal reasoning tasks

### Image Quality
- Use high-resolution images for better text recognition
- Ensure good contrast for document analysis
- Crop images to focus on relevant content
- Consider file size limits (20MB max after processing)

### Prompt Engineering
- Be specific about what you want to extract or analyze
- Use structured prompts for consistent outputs
- Provide context about the image type or domain
- Ask for specific formats (JSON, markdown, etc.) when needed

### Error Handling
- Always check for error responses
- Handle network timeouts for URL-based images
- Validate image formats before sending
- Have fallback strategies for failed requests

## Troubleshooting

### Common Issues

**1. Image not found**
```
Error: Could not load image from path: /path/to/image.jpg
```
- Check that the file path is correct
- Ensure the file exists and is readable
- Use absolute paths when possible

**2. Invalid image format**
```
Error: Unsupported image format: .bmp
```
- Convert to supported format (JPEG, PNG, GIF, WebP)
- Check that the file isn't corrupted

**3. Image too large**
```
Warning: Image resized for API optimization
```
- This is normal for large images
- The server automatically handles resizing

**4. Network errors with URLs**
```
Error: Failed to fetch image from URL
```
- Check that the URL is accessible
- Verify the image URL is direct (not behind authentication)
- Try downloading and using file path instead

**5. Model not supporting vision**
```
Error: Model does not support vision capabilities
```
- Use `list_vision_models` to get supported models
- Switch to a vision-capable model

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
npx openrouter-mcp start --debug
```

This will show detailed logs of image processing steps.

## Examples

See the `examples/multimodal_example.py` file for complete working examples of:
- Basic image analysis
- Multiple image comparison
- URL-based image processing
- Base64 image handling

Run the examples:

```bash
cd examples
python multimodal_example.py
```

## API Reference

For detailed API documentation, see the [API Documentation](API.md#vision-endpoints).

## Limitations

- Maximum image size: 20MB (after automatic resizing)
- Rate limits apply per OpenRouter plan
- Vision capabilities vary by model
- Some models may have token limits affecting image analysis depth

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0