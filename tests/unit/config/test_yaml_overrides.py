from __future__ import annotations

from src.config import settings as settings_module
from src.config.settings import Settings, apply_yaml_overrides


def test_apply_yaml_overrides_loads_nested_sections(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        (
            "app:\n"
            "  debug: false\n"
            "  log_level: DEBUG\n"
            "  display:\n"
            "    verbose: true\n"
            "middleware:\n"
            "  rate_limit:\n"
            "    enabled: false\n"
        ),
        encoding="utf-8",
    )

    settings = Settings()
    original_candidates = settings_module._config_path_candidates
    settings_module._config_path_candidates = lambda _data_path: [config_path]
    try:
        apply_yaml_overrides(settings)
    finally:
        settings_module._config_path_candidates = original_candidates

    assert settings.app.debug is False
    assert settings.log_level == "DEBUG"
    assert settings.display_verbose is True
    assert settings.middleware.rate_limit.enabled is False
