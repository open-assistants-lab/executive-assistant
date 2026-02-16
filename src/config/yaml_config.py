"""YAML configuration loader for admin-managed settings.

This module provides functionality to load YAML configuration files
and validate them using Pydantic models.

Configuration is admin-managed only:
- Single config file: /data/config.yaml
- No user-level overrides
- Env vars reserved for API keys and URLs (not middleware config)

Example:
    from src.config.yaml_config import load_yaml_config
    from src.config.middleware_settings import MiddlewareConfig

    config = load_yaml_config(
        path=Path("/data/config.yaml"),
        model_class=MiddlewareConfig
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def load_yaml_config(path: Path, model_class: type[T]) -> T:
    """Load and validate YAML configuration using a Pydantic model.

    Args:
        path: Path to YAML configuration file
        model_class: Pydantic model class for validation

    Returns:
        Validated configuration instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValidationError: If config doesn't match schema
        ValueError: If config file is invalid

    Example:
        ```python
        config = load_yaml_config(
            path=Path("/data/config.yaml"),
            model_class=MiddlewareConfig
        )
        ```
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            f"Please create {path} or use default configuration."
        )

    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required to load configuration. "
            "Install it with: uv add pyyaml"
        )

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(
            f"Invalid YAML in {path}: {e}\n"
            f"Please fix the YAML syntax."
        )

    if data is None:
        # Empty file - return defaults
        return model_class()

    if not isinstance(data, dict):
        raise ValueError(
            f"Configuration must be a dictionary, got {type(data).__name__}\n"
            f"Please check the format of {path}"
        )

    try:
        return model_class(**data)
    except ValidationError as e:
        raise ValidationError(
            f"Configuration validation failed for {path}:\n"
            f"{str(e)}\n"
            f"Please fix the configuration errors.",
            model_class
        )


def load_yaml_config_with_default(
    path: Path,
    model_class: type[T],
) -> T:
    """Load YAML config with fallback to defaults if file doesn't exist.

    This is useful for optional configuration files where defaults
    should be used if the file is missing.

    Args:
        path: Path to YAML configuration file
        model_class: Pydantic model class for validation

    Returns:
        Validated configuration instance (from file or defaults)

    Example:
        ```python
        config = load_yaml_config_with_default(
            path=Path("/data/config.yaml"),
            model_class=MiddlewareConfig
        )
        # Returns defaults if file doesn't exist
        ```
    """
    if not path.exists():
        return model_class()

    return load_yaml_config(path, model_class)
