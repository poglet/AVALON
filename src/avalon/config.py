"""Configuration loading for AVALON.

Precedence (highest wins): CLI flag > environment/.env > ``config.toml`` >
built-in default.

The built-in defaults live in the bundled ``data/config.toml``. A project may
override them with its own ``.avalon/config.toml``. Environment variables use the
``AVALON_`` prefix (e.g. ``AVALON_MODEL``). The OpenRouter API key is read from
``OPENROUTER_API_KEY`` and is never stored in ``config.toml``.

For safety, ``.env`` is loaded only from the current working directory, not from
parent directories, so an unexpected ``.env`` higher up the tree cannot silently
influence configuration.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

DEFAULT_CONFIG_PATH = Path(__file__).parent / "data" / "config.toml"

BoxType = Literal["black", "grey", "white"]
OutputFormat = Literal["rich", "plain", "json"]


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


class Settings(BaseModel):
    """Resolved, validated AVALON settings."""

    model: str = "deepseek/deepseek-v4.1-flash"
    backup_model: str = ""
    max_steps: int = 40
    max_time_minutes: int | None = None
    box_type: BoxType = "white"
    playbook_dir: str = "playbooks"
    output_format: OutputFormat = "rich"


# Environment variable -> Settings field.
_ENV_KEYS: dict[str, str] = {
    "AVALON_MODEL": "model",
    "AVALON_BACKUP_MODEL": "backup_model",
    "AVALON_MAX_STEPS": "max_steps",
    "AVALON_MAX_TIME_MINUTES": "max_time_minutes",
    "AVALON_BOX_TYPE": "box_type",
    "AVALON_PLAYBOOK_DIR": "playbook_dir",
    "AVALON_OUTPUT_FORMAT": "output_format",
}


def _load_env() -> None:
    """Load ``.env`` from the current working directory only."""
    load_dotenv(dotenv_path=Path.cwd() / ".env")


def _read_toml(path: Path) -> dict[str, Any]:
    """Read a TOML file, returning an empty mapping if it does not exist."""
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not read config file {path}: {exc}") from exc


def _env_overrides() -> dict[str, Any]:
    """Collect non-empty ``AVALON_*`` environment variables."""
    overrides: dict[str, Any] = {}
    for env_key, field in _ENV_KEYS.items():
        value = os.environ.get(env_key)
        if value is not None and value.strip() != "":
            overrides[field] = value
    return overrides


def load_settings(
    config_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    """Resolve settings from defaults, ``config.toml``, env, and explicit overrides.

    ``overrides`` is typically built from CLI flags; ``None`` values are ignored
    so that an unset flag does not clobber a lower-precedence value.
    """
    _load_env()

    data: dict[str, Any] = _read_toml(DEFAULT_CONFIG_PATH)
    if config_path is not None:
        data.update(_read_toml(config_path))
    data.update(_env_overrides())
    if overrides:
        data.update({k: v for k, v in overrides.items() if v is not None})

    try:
        return Settings(**data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration: {exc}") from exc


def get_api_key() -> str:
    """Return the OpenRouter API key from the environment, or raise."""
    _load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ConfigError(
            "OPENROUTER_API_KEY is not set. Add it to .env or export it in your environment."
        )
    return key
