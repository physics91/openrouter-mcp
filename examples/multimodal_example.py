#!/usr/bin/env python3
"""
Example script demonstrating multimodal capabilities of OpenRouter MCP Server.

This script shows how to use the vision features to analyze images with AI models.
"""

import asyncio
import base64
import os
from pathlib import Path
from PIL import Image
import io

# Add parent directory to path to import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.openrouter_mcp.client.openrouter import OpenRouterClient
from src.openrouter_mcp.handlers.multimodal import (
    encode_image_to_base64,
    process_image,
    is_vision_model,
    get_vision_model_names
)


async def test_vision_with_generated_image():
    """Test vision capabilities with a programmatically generated image."""
    print("\n=== Testing Vision with Generated Image ===\n")
    
    # Create a simple test image
    img = Image.new('RGB', (400, 300), color='lightblue')
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    
    # Draw some shapes and text
    draw.rectangle([50, 50, 150, 150], fill='red', outline='black', width=3)
    draw.ellipse([200, 50, 350, 200], fill='green', outline='black', width=3)
    draw.text((100, 220), "OpenRouter MCP", fill='black')
    draw.text((120, 250), "Vision Test", fill='blue')
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes = img_bytes.getvalue()
    
    # Process and encode the image
    base64_img = encode_image_to_base64(img_bytes)
    processed_img, was_resized = process_image(base64_img)
    if was_resized:
        print("Image was resized for API optimization")
    
    # Create OpenRouter client
    client = OpenRouterClient.from_env()
    
    # Format the message with image
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe what you see in this image. What shapes and colors are present?"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{processed_img}"}}
            ]
        }
    ]
    
    # Use a vision-capable model
    model = "openai/gpt-4o-mini"  # Fast and affordable vision model
    
    print(f"Using model: {model}")
    print("Sending image for analysis...")
    
    try:
        async with client:
            response = await client.chat_completion_with_vision(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            # Extract and display the response
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                print(f"\nAI Response:\n{content}")
                
                # Show usage stats if available
                if "usage" in response:
                    usage = response["usage"]
                    print(f"\nTokens used: {usage.get('total_tokens', 'N/A')}")
            else:
                print("No response received")
                
    except Exception as e:
        print(f"Error: {str(e)}")


async def test_vision_with_url():
    """Test vision capabilities with an image URL."""
    print("\n=== Testing Vision with Image URL ===\n")
    
    # Use a public image URL
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/320px-Cat03.jpg"
    
    # Create OpenRouter client
    client = OpenRouterClient.from_env()
    
    # Format the message with image URL
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What animal is in this image? Describe it briefly."},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }
    ]
    
    # Use a vision-capable model
    model = "openai/gpt-4o-mini"
    
    print(f"Using model: {model}")
    print(f"Image URL: {image_url}")
    print("Sending image URL for analysis...")
    
    try:
        async with client:
            response = await client.chat_completion_with_vision(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            
            # Extract and display the response
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                print(f"\nAI Response:\n{content}")
            else:
                print("No response received")
                
    except Exception as e:
        print(f"Error: {str(e)}")


async def list_vision_models():
    """List all available vision-capable models."""
    print("\n=== Available Vision Models ===\n")
    
    # Sample vision models (in real implementation, would query OpenRouter API)
    vision_models = [
        "openai/gpt-4o",
        "openai/gpt-4o-mini", 
        "anthropic/claude-3-opus",
        "anthropic/claude-3-sonnet",
        "anthropic/claude-3-haiku",
        "google/gemini-pro-vision",
        "meta-llama/llama-3.2-90b-vision-instruct",
        "meta-llama/llama-3.2-11b-vision-instruct"
    ]
    
    print(f"Common vision-capable models:\n")
    for model in vision_models:
        print(f"  - {model}")
    
    print("\nNote: Actual availability may depend on your OpenRouter account and API access.")


async def test_multiple_images():
    """Test analyzing multiple images in one request."""
    print("\n=== Testing Multiple Images ===\n")
    
    # Create two simple test images
    # Image 1: Blue square
    img1 = Image.new('RGB', (200, 200), color='blue')
    draw1 = ImageDraw.Draw(img1)
    draw1.text((70, 90), "Image 1", fill='white')
    
    # Image 2: Red circle
    img2 = Image.new('RGB', (200, 200), color='white')
    draw2 = ImageDraw.Draw(img2)
    draw2.ellipse([25, 25, 175, 175], fill='red', outline='black', width=2)
    draw2.text((70, 90), "Image 2", fill='white')
    
    # Convert to base64
    img1_bytes = io.BytesIO()
    img2_bytes = io.BytesIO()
    img1.save(img1_bytes, format='PNG')
    img2.save(img2_bytes, format='PNG')
    
    base64_img1 = encode_image_to_base64(img1_bytes.getvalue())
    base64_img2 = encode_image_to_base64(img2_bytes.getvalue())
    
    # Create OpenRouter client
    client = OpenRouterClient.from_env()
    
    # Format message with multiple images
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Compare these two images. What are the main differences in color and shape?"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img1}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img2}"}}
            ]
        }
    ]
    
    model = "openai/gpt-4o-mini"
    
    print(f"Using model: {model}")
    print("Sending 2 images for comparison...")
    
    try:
        async with client:
            response = await client.chat_completion_with_vision(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                print(f"\nAI Response:\n{content}")
            else:
                print("No response received")
                
    except Exception as e:
        print(f"Error: {str(e)}")


async def main():
    """Run all multimodal examples."""
    print("=" * 60)
    print("OpenRouter MCP Multimodal Examples")
    print("=" * 60)
    
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("\nError: OPENROUTER_API_KEY environment variable not set")
        print("Please set your OpenRouter API key to run these examples")
        return
    
    # Run examples
    await list_vision_models()
    await test_vision_with_generated_image()
    await test_vision_with_url()
    await test_multiple_images()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())