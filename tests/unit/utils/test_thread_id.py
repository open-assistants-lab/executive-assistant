from __future__ import annotations

import re

from src.utils.thread_id import create_thread_id


def test_create_thread_id_contains_expected_components() -> None:
    thread_id = create_thread_id(user_id="User 123", channel="telegram", reason="clear")
    assert thread_id.startswith("telegram-user-123-clear-")
    assert re.match(
        r"^telegram-user-123-clear-\d{14}-[a-f0-9]{8}$",
        thread_id,
    )


def test_create_thread_id_is_unique() -> None:
    first = create_thread_id(user_id="u1", channel="api", reason="session")
    second = create_thread_id(user_id="u1", channel="api", reason="session")
    assert first != second
