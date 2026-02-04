#!/usr/bin/env python3
"""Quick test script to verify Ollama Cloud API works."""

import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from executive_assistant.config import settings

# Load credentials from .env
load_dotenv("docker/.env")

# Verify credentials are loaded
api_key = settings.OLLAMA_CLOUD_API_KEY
cloud_url = settings.OLLAMA_CLOUD_URL

print("="*60)
print("OLLAMA CLOUD API TEST")
print("="*60)
print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
print(f"Cloud URL: {cloud_url}")
print("="*60)

# Test with a simple prompt
models_to_test = [
    "deepseek-v3.2:cloud",
    "qwen3-next:80b-cloud",
    "gpt-oss:20b-cloud",
]

for model in models_to_test:
    try:
        print(f"\n🧠 Testing: {model}")
        print(f"{'-'*60}")

        llm = ChatOllama(
            model=model,
            base_url=cloud_url,
            temperature=0.7,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {api_key}"
                }
            }
        )

        # Simple test prompt
        response = llm.invoke("Say 'Hello, this is a test!' in one sentence.")

        print(f"✅ Response: {response.content}")

        # Show token usage if available
        if hasattr(response, 'usage_metadata'):
            print(f"📊 Token Usage:")
            print(f"   Input:  {response.usage_metadata.get('input_tokens', 'N/A')}")
            print(f"   Output: {response.usage_metadata.get('output_tokens', 'N/A')}")
            print(f"   Total:  {response.usage_metadata.get('total_tokens', 'N/A')}")
        else:
            print(f"⚠️  Token usage metadata not available")

        print(f"✅ SUCCESS: {model} works!")
        print("="*60)

    except Exception as e:
        print(f"❌ FAILED: {model}")
        print(f"   Error: {e}")
        print("="*60)

print("\n✅ Test complete!")
