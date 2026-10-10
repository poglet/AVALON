"""AVALON command-line interface.

Phase 0 provides only the skeleton: a Typer app with ``--version`` and a
placeholder ``doctor`` command. The full subcommand surface
(``run``/``resume``/``runs``/``show``/``steer``/``export``/``doctor``) is wired
up in later phases.
"""

from __future__ import annotations

import typer

from avalon import __version__

app = typer.Typer(
    name="avalon",
    help="AVALON — autonomous pentesting framework.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"avalon {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the AVALON version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """AVALON — Automated Vulnerability Analysis and Logical Offensive Network."""


@app.command()
def doctor() -> None:
    """Check host tool availability and print install hints."""
    typer.echo("avalon doctor: not yet implemented (Phase 2)")


if __name__ == "__main__":  # pragma: no cover
    app()
