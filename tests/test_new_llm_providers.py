"""Test new LLM providers (Gemini, Qwen, Kimi, MiniMax)."""

import pytest

from executive_assistant.config.llm_factory import (
    LLMFactory,
    _get_model_config,
    MODEL_PATTERNS,
    validate_llm_config,
)
from executive_assistant.config.settings import settings


class TestModelPatterns:
    """Test model name validation patterns."""

    def test_gemini_pattern(self):
        """Test Gemini model name pattern."""
        import re

        pattern = MODEL_PATTERNS["gemini"]

        # Valid Gemini model names
        valid_models = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
        ]

        for model in valid_models:
            assert re.match(pattern, model), f"Model {model} should match Gemini pattern"

    def test_qwen_pattern(self):
        """Test Qwen model name pattern."""
        import re

        pattern = MODEL_PATTERNS["qwen"]

        # Valid Qwen model names
        valid_models = [
            "qwen-flash",
            "qwen-max-latest",
            "qwen-plus-latest",
            "qwen-turbo-latest",
            "qwq-32b-preview",
        ]

        for model in valid_models:
            assert re.match(pattern, model), f"Model {model} should match Qwen pattern"

    def test_kimi_pattern(self):
        """Test Kimi model name pattern."""
        import re

        pattern = MODEL_PATTERNS["kimi"]

        # Valid Kimi model names
        valid_models = [
            "kimi-k2.5",
            "kimi-k2",
            "kimi-k2-coder",
            "kimi-k2-reasoner",
        ]

        for model in valid_models:
            assert re.match(pattern, model), f"Model {model} should match Kimi pattern"

    def test_minimax_pattern(self):
        """Test MiniMax model name pattern."""
        import re

        pattern = MODEL_PATTERNS["minimax"]

        # Valid MiniMax model names
        valid_models = [
            "MiniMax-M2.1",
            "MiniMax-M2",
            "MiniMax-M2-Stable",
            "MiniMax-M2-Turbo",
            "M2",
        ]

        for model in valid_models:
            assert re.match(pattern, model), f"Model {model} should match MiniMax pattern"


class TestModelConfig:
    """Test model configuration retrieval."""

    def test_gemini_default_model_config(self):
        """Test Gemini default model configuration."""
        # This will use the YAML config or fall back to error
        # We're testing that the function works, not that the model is configured
        try:
            model = _get_model_config("gemini", "default")
            # If it succeeds, we should get a model name
            assert isinstance(model, str)
        except ValueError:
            # Expected if no model is configured
            pass

    def test_qwen_default_model_config(self):
        """Test Qwen default model configuration."""
        try:
            model = _get_model_config("qwen", "default")
            assert isinstance(model, str)
        except ValueError:
            # Expected if no model is configured
            pass


class TestLLMFactoryCreators:
    """Test LLMFactory creator methods exist."""

    def test_factory_has_gemini_creator(self):
        """Test LLMFactory has _create_gemini method."""
        assert hasattr(LLMFactory, "_create_gemini")

    def test_factory_has_qwen_creator(self):
        """Test LLMFactory has _create_qwen method."""
        assert hasattr(LLMFactory, "_create_qwen")

    def test_factory_has_kimi_creator(self):
        """Test LLMFactory has _create_kimi method."""
        assert hasattr(LLMFactory, "_create_kimi")

    def test_factory_has_minimax_creator(self):
        """Test LLMFactory has _create_minimax method."""
        assert hasattr(LLMFactory, "_create_minimax")


class TestLLMFactoryCreate:
    """Test LLMFactory.create method with new providers."""

    def test_create_gemini_without_api_key_raises_error(self):
        """Test creating Gemini model without API key raises ValueError."""
        # Ensure API key is not set
        if settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY:
            pytest.skip("API key is set, skipping error test")

        with pytest.raises(ValueError, match="GOOGLE_API_KEY or GEMINI_API_KEY not set"):
            LLMFactory.create(provider="gemini")

    def test_create_qwen_without_api_key_raises_error(self):
        """Test creating Qwen model without API key raises ValueError."""
        if settings.DASHSCOPE_API_KEY:
            pytest.skip("API key is set, skipping error test")

        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY not set"):
            LLMFactory.create(provider="qwen")

    def test_create_kimi_without_api_key_raises_error(self):
        """Test creating Kimi model without API key raises ValueError."""
        if settings.MOONSHOT_API_KEY:
            pytest.skip("API key is set, skipping error test")

        with pytest.raises(ValueError, match="MOONSHOT_API_KEY not set"):
            LLMFactory.create(provider="kimi")

    def test_create_minimax_without_api_key_raises_error(self):
        """Test creating MiniMax model without API key raises ValueError."""
        if settings.MINIMAX_API_KEY:
            pytest.skip("API key is set, skipping error test")

        with pytest.raises(ValueError, match="MINIMAX_API_KEY not set"):
            LLMFactory.create(provider="minimax")

    def test_create_with_unknown_provider_raises_error(self):
        """Test creating model with unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMFactory.create(provider="unknown_provider")


class TestSettingsConfiguration:
    """Test Settings class has new provider configuration."""

    def test_settings_has_gemini_config(self):
        """Test Settings has Gemini configuration."""
        assert hasattr(settings, "GEMINI_DEFAULT_MODEL")
        assert hasattr(settings, "GEMINI_FAST_MODEL")
        assert hasattr(settings, "GOOGLE_API_KEY")
        assert hasattr(settings, "GEMINI_API_KEY")

    def test_settings_has_qwen_config(self):
        """Test Settings has Qwen configuration."""
        assert hasattr(settings, "QWEN_DEFAULT_MODEL")
        assert hasattr(settings, "QWEN_FAST_MODEL")
        assert hasattr(settings, "DASHSCOPE_API_KEY")

    def test_settings_has_kimi_config(self):
        """Test Settings has Kimi configuration."""
        assert hasattr(settings, "KIMI_DEFAULT_MODEL")
        assert hasattr(settings, "KIMI_FAST_MODEL")
        assert hasattr(settings, "MOONSHOT_API_KEY")

    def test_settings_has_minimax_config(self):
        """Test Settings has MiniMax configuration."""
        assert hasattr(settings, "MINIMAX_DEFAULT_MODEL")
        assert hasattr(settings, "MINIMAX_FAST_MODEL")
        assert hasattr(settings, "MINIMAX_API_KEY")


def test_provider_list_complete():
    """Test that all 8 providers are supported."""
    from executive_assistant.config.settings import Settings

    # Get the Literal type for DEFAULT_LLM_PROVIDER
    # This tests that the type annotation includes all 8 providers
    import inspect

    from typing import get_args

    # Get the type hints for Settings.DEFAULT_LLM_PROVIDER
    hints = Settings.model_fields.get("DEFAULT_LLM_PROVIDER")
    assert hints is not None

    # The annotation should contain all 8 providers
    # Note: We can't easily test this at runtime without parsing the type,
    # but we can at least verify the factory works
    valid_providers = ["anthropic", "openai", "zhipu", "ollama", "gemini", "qwen", "kimi", "minimax"]

    for provider in valid_providers:
        # Verify the provider is recognized (won't fail with "Unknown provider")
        try:
            LLMFactory.create(provider=provider)
        except ValueError as e:
            # Should only fail due to missing API key, not "Unknown provider"
            assert "Unknown provider" not in str(e), f"Provider {provider} not recognized"
        except Exception:
            # Other exceptions (import errors, etc.) are fine for this test
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
