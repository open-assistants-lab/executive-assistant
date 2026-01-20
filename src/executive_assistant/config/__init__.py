"""Configuration module for Executive Assistant."""

from executive_assistant.config.settings import Settings, settings
from executive_assistant.config.llm_factory import LLMFactory, create_model

__all__ = ["Settings", "settings", "LLMFactory", "create_model"]
