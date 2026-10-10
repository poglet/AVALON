"""Phase 0 smoke tests: the package imports and the CLI is wired up."""

from __future__ import annotations

from typer.testing import CliRunner

from avalon import __version__
from avalon.cli import app

runner = CliRunner()


def test_version_is_exposed() -> None:
    assert __version__ == "0.1.0"


def test_cli_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_doctor_placeholder() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout
