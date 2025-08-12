#!/usr/bin/env python3
"""
OpenRouter API direct test to check available models
"""

import asyncio
import os
import aiohttp
import json


async def test_openrouter_api():
    print('OpenRouter API Direct Test')
    print('=' * 40)
    
    api_key = "placeholder"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'HTTP-Referer': 'https://localhost',
        'X-Title': 'OpenRouter MCP Server Test',
        'Content-Type': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test models endpoint
            print('Testing /api/v1/models endpoint...')
            async with session.get(
                'https://openrouter.ai/api/v1/models',
                headers=headers
            ) as response:
                print(f'Response status: {response.status}')
                
                if response.status == 200:
                    data = await response.json()
                    models = data.get('data', [])
                    print(f'Models returned: {len(models)}')
                    
                    if models:
                        print('\nSample models:')
                        for i, model in enumerate(models[:5]):
                            print(f'{i+1}. {model.get("id", "unknown")} - {model.get("name", "No name")}')
                            if 'context_length' in model:
                                print(f'   Context: {model["context_length"]:,} tokens')
                            if 'pricing' in model:
                                pricing = model['pricing']
                                prompt_price = pricing.get('prompt', '0')
                                completion_price = pricing.get('completion', '0')
                                print(f'   Pricing: ${prompt_price}/1K prompt, ${completion_price}/1K completion')
                    else:
                        print('No models returned in data array')
                else:
                    text = await response.text()
                    print(f'Error response: {text}')
                    
        except Exception as e:
            print(f'Request failed: {e}')
            
        try:
            # Test chat completion to verify API key works
            print('\nTesting chat completion endpoint...')
            chat_payload = {
                "model": "meta-llama/llama-3.2-3b-instruct:free",
                "messages": [
                    {"role": "user", "content": "Hello, respond with just 'API works'"}
                ],
                "max_tokens": 10
            }
            
            async with session.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=chat_payload
            ) as response:
                print(f'Chat response status: {response.status}')
                
                if response.status == 200:
                    data = await response.json()
                    if 'choices' in data and data['choices']:
                        content = data['choices'][0]['message']['content']
                        print(f'Response: {content}')
                        print('Chat completion successful!')
                    else:
                        print('No choices in response')
                else:
                    text = await response.text()
                    print(f'Chat error response: {text}')
                    
        except Exception as e:
            print(f'Chat request failed: {e}')


if __name__ == "__main__":
    asyncio.run(test_openrouter_api())