"""Shared fixtures for storage tests — ensure clean path state between tests."""

import os

import pytest


@pytest.fixture(autouse=True)
def reset_path_state():
    """Clear settings and paths cache before each storage test.

    Also clears DEPLOYMENT_EA_ROOT and DEPLOYMENT_DATA_PATH that
    the session-scoped API conftest may have left in os.environ.
    """
    saved = {}
    for var in ("DEPLOYMENT_EA_ROOT", "DEPLOYMENT_DATA_PATH", "DEPLOYMENT_MODE"):
        saved[var] = os.environ.pop(var, None)
    from src.config.settings import reload_settings
    from src.storage.paths import _paths_cache

    reload_settings()
    _paths_cache.clear()
    yield
    _paths_cache.clear()
    for var, val in saved.items():
        if val is not None:
            os.environ[var] = val
