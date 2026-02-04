#!/usr/bin/env python3
"""Quick test script to verify Qwen provider works."""

import os
import sys

# Add src to path
sys.path.insert(0, "src")

from executive_assistant.config.llm_factory import LLMFactory
from executive_assistant.config.settings import settings


def test_qwen_provider():
    """Test Qwen provider configuration and model creation."""
    print("=" * 60)
    print("Testing Qwen Provider")
    print("=" * 60)

    # Check settings
    print(f"\n1. Provider Settings:")
    print(f"   DEFAULT_LLM_PROVIDER: {settings.DEFAULT_LLM_PROVIDER}")
    print(f"   DASHSCOPE_API_KEY: {'✓ Set' if settings.DASHSCOPE_API_KEY else '✗ Not set'}")

    # Check model configuration
    print(f"\n2. Model Configuration:")
    print(f"   QWEN_DEFAULT_MODEL: {settings.QWEN_DEFAULT_MODEL}")
    print(f"   QWEN_FAST_MODEL: {settings.QWEN_FAST_MODEL}")

    # Test model creation
    print(f"\n3. Testing Model Creation:")
    try:
        # Create default model
        model = LLMFactory.create(provider="qwen", model="default")
        print(f"   ✓ Created default Qwen model: {model.model_name}")

        # Test simple invocation
        print(f"\n4. Testing Simple Invocation:")
        response = model.invoke("Hello! Please respond with 'Qwen is working!' in exactly this format.")
        print(f"   Response: {response.content[:100]}...")

        if "Qwen is working!" in response.content or "working" in response.content.lower():
            print(f"\n✅ SUCCESS: Qwen provider is working correctly!")
            return True
        else:
            print(f"\n⚠️  WARNING: Unexpected response from Qwen")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_qwen_provider()
    sys.exit(0 if success else 1)
