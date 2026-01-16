"""Pytest configuration for VCR-based integration tests."""

import pytest


@pytest.fixture(scope="session")
def vcr_config():
    """Default VCR configuration for recording/replaying HTTP."""
    return {
        "cassette_library_dir": "tests/cassettes",
        "filter_headers": [
            ("authorization", "XXXX"),
            ("x-api-key", "XXXX"),
        ],
        "filter_query_parameters": [
            ("api_key", "XXXX"),
            ("key", "XXXX"),
        ],
        "filter_post_data_parameters": [
            ("api_key", "XXXX"),
            ("key", "XXXX"),
        ],
    }
