"""Configuration loader that merges YAML defaults with .env overrides."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _load_yaml_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load YAML configuration file.

    Args:
        config_path: Path to YAML file. If None, uses config.yaml at project root.

    Returns:
        Parsed YAML as dictionary, or empty dict if file not found.
    """
    import yaml

    if config_path is None:
        # Try to find config.yaml at project root
        # This file is at: src/cassey/config/loader.py
        # Go up from src/cassey/config to project root
        this_file = Path(__file__).resolve()
        config_path = this_file.parent.parent.parent.parent / "config.yaml"

    config_path = Path(config_path).resolve()

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        logger.debug(f"Loaded config from {config_path}")
        return data
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return {}


def _flatten_yaml_dict(yaml_data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested YAML dict into env-var style keys.

    Example:
        {"llm": {"default_provider": "anthropic"}} -> {"LLM_DEFAULT_PROVIDER": "anthropic"}

    Args:
        yaml_data: Nested dictionary from YAML.
        prefix: Current key prefix (for recursion).

    Returns:
        Flattened dictionary with uppercase keys.
    """
    result: dict[str, Any] = {}

    for key, value in yaml_data.items():
        # Build new key with prefix
        new_key = f"{prefix}_{key}".upper() if prefix else key.upper()

        if isinstance(value, dict):
            # Recurse into nested dict
            result.update(_flatten_yaml_dict(value, new_key))
        elif isinstance(value, list):
            # Convert lists to comma-separated strings for env compatibility
            result[new_key] = ",".join(str(v) for v in value) if value else ""
        elif value is None:
            # None -> empty string (will be parsed as None by Pydantic)
            result[new_key] = ""
        else:
            result[new_key] = value

    return result


class ConfigLoader:
    """Loads and merges configuration from YAML and .env files.

    Load order (later overrides earlier):
    1. YAML default values (config.yaml at project root)
    2. Environment variables (.env file or system env)

    Usage:
        loader = ConfigLoader()
        settings = loader.load_settings(Settings)
    """

    def __init__(self, config_path: Path | str | None = None):
        """Initialize loader.

        Args:
            config_path: Optional path to YAML config file.
        """
        self.config_path = config_path
        self._yaml_defaults: dict[str, Any] = {}

    def load_yaml_defaults(self) -> dict[str, Any]:
        """Load and flatten YAML configuration.

        Returns:
            Flattened dictionary suitable for Pydantic Settings.
        """
        yaml_data = _load_yaml_config(self.config_path)
        self._yaml_defaults = _flatten_yaml_dict(yaml_data)
        return self._yaml_defaults

    def get_settings_kwargs(self) -> dict[str, Any]:
        """Get kwargs for Pydantic Settings initialization.

        YAML values are passed as defaults, env vars take precedence.

        Returns:
            Dictionary of settings values.
        """
        if not self._yaml_defaults:
            self.load_yaml_defaults()

        return self._yaml_defaults.copy()


# Cached loader instance
_loader: ConfigLoader | None = None


def get_config_loader(config_path: Path | str | None = None) -> ConfigLoader:
    """Get cached config loader instance.

    Args:
        config_path: Optional path to YAML config file.

    Returns:
        ConfigLoader instance.
    """
    global _loader

    if _loader is None or config_path is not None:
        _loader = ConfigLoader(config_path)

    return _loader


def get_yaml_defaults() -> dict[str, Any]:
    """Get flattened YAML defaults.

    Returns:
        Flattened dictionary from YAML config.
    """
    return get_config_loader().load_yaml_defaults()


# Custom Pydantic settings that uses YAML defaults
def create_settings_class(
    base_class: type[BaseSettings] = BaseSettings,
    config_path: Path | str | None = None,
) -> type[BaseSettings]:
    """Create a Settings class that loads from YAML + .env.

    Args:
        base_class: Base Settings class to extend.
        config_path: Optional path to YAML config file.

    Returns:
        Settings class with YAML defaults pre-loaded.
    """
    yaml_defaults = get_config_loader(config_path).load_yaml_defaults()

    # Create a custom Settings class with defaults from YAML
    class YAMLSettings(base_class):
        """Settings with YAML defaults and .env overrides."""

        # Field defaults will be set from YAML
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )

        def __init__(self, **kwargs):
            # Merge YAML defaults with provided kwargs
            # kwargs take precedence over YAML
            merged = {**yaml_defaults, **kwargs}
            super().__init__(**merged)

    return YAMLSettings
