"""Tests for the configuration loader and precedence rules."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from avalon import config
from avalon.config import ConfigError, get_api_key, load_settings


@pytest.fixture(autouse=True)
def _clear_avalon_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("AVALON_"):
            monkeypatch.delenv(key, raising=False)


def test_defaults_come_from_bundled_config() -> None:
    settings = load_settings()
    assert settings.model == "deepseek/deepseek-v4.1-flash"
    assert settings.backup_model == ""
    assert settings.max_steps == 40
    assert settings.box_type == "white"
    assert settings.output_format == "rich"


def test_config_file_overrides_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "custom/model"\nmax_steps = 7\n', encoding="utf-8")
    settings = load_settings(config_path=cfg)
    assert settings.model == "custom/model"
    assert settings.max_steps == 7


def test_env_overrides_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "file/model"\n', encoding="utf-8")
    monkeypatch.setenv("AVALON_MODEL", "env/model")
    settings = load_settings(config_path=cfg)
    assert settings.model == "env/model"


def test_flag_overrides_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVALON_MODEL", "env/model")
    settings = load_settings(overrides={"model": "flag/model"})
    assert settings.model == "flag/model"


def test_none_overrides_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVALON_MODEL", "env/model")
    settings = load_settings(overrides={"model": None, "max_steps": None})
    assert settings.model == "env/model"


def test_invalid_box_type_raises() -> None:
    with pytest.raises(ConfigError):
        load_settings(overrides={"box_type": "purple"})


def test_get_api_key_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
    assert get_api_key() == "sk-test-123"


def test_get_api_key_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(ConfigError):
        get_api_key()
