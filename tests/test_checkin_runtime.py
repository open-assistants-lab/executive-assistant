from __future__ import annotations

from datetime import datetime, timedelta, timezone

from executive_assistant.checkin.config import (
    CheckinConfig,
    get_checkin_config,
    get_users_with_checkin_enabled,
    save_checkin_config,
)
from executive_assistant.checkin.runner import should_run_checkin
from executive_assistant.config import settings


def _set_all_days(config: CheckinConfig) -> CheckinConfig:
    config.active_days = "Mon,Tue,Wed,Thu,Fri,Sat,Sun"
    config.active_hours_start = "00:00"
    config.active_hours_end = "23:59"
    return config


def test_get_users_with_checkin_enabled_scans_user_checkin_dbs(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "USERS_ROOT", tmp_path / "users")

    enabled_cfg = _set_all_days(CheckinConfig(thread_id="http:enabled", enabled=True))
    disabled_cfg = _set_all_days(CheckinConfig(thread_id="http:disabled", enabled=False))

    save_checkin_config(enabled_cfg)
    save_checkin_config(disabled_cfg)

    users = get_users_with_checkin_enabled()
    assert users == ["http:enabled"]


def test_get_checkin_config_persist_default_writes_row(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "USERS_ROOT", tmp_path / "users")

    cfg = get_checkin_config("http:new_user", persist_default=True)
    assert cfg.thread_id == "http:new_user"
    assert cfg.enabled is True

    users = get_users_with_checkin_enabled()
    assert "http:new_user" in users


def test_should_run_checkin_supports_iso_timestamps() -> None:
    config = _set_all_days(CheckinConfig(thread_id="http:test", enabled=True, every="30m"))

    now_iso = datetime.now(timezone.utc).isoformat()
    assert should_run_checkin(config, now_iso) is False

    old_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert should_run_checkin(config, old_iso) is True
