"""Phase 0 smoke tests: the package imports and the CLI surface is wired up."""

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


def test_cli_exposes_documented_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("run", "resume", "runs", "show", "steer", "export", "doctor"):
        assert command in result.stdout


def test_cli_run_is_a_stub() -> None:
    result = runner.invoke(app, ["run", "--project", "demo", "--target", "10.0.0.1"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output


def test_cli_doctor_runs() -> None:
    result = runner.invoke(app, ["doctor"])
    # Exit 0 when all required tools are present, 1 when some are missing.
    assert result.exit_code in (0, 1)
    assert "host tool check" in result.output
