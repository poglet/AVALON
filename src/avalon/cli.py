"""AVALON command-line interface.

Phase 0 provides the full documented subcommand surface as stubs. Each command
prints a clear "not yet implemented" message and exits non-zero, so the CLI
matches the plan and ``--help`` is honest while the engine is built out in
later phases.
"""

from __future__ import annotations

from typing import Annotated

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


def _not_implemented(command: str, phase: str) -> None:
    typer.echo(
        f"avalon {command}: not yet implemented (planned for {phase}).\n"
        "AVALON is at v0.1 Phase 0 (scaffolding); the engine is being built out.",
        err=True,
    )
    raise typer.Exit(code=1)


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
def run(
    project: Annotated[str | None, typer.Option(help="Project name (the run identity).")] = None,
    target: Annotated[
        list[str] | None,
        typer.Option(help="In-scope target (host/IP/CIDR/domain/URL). Repeatable."),
    ] = None,
    box_type: Annotated[
        str, typer.Option(help="Engagement type: black, grey, or white.")
    ] = "white",
    cred: Annotated[
        list[str] | None,
        typer.Option(
            help=(
                "Provided credential as user:pass. Repeatable. WARNING: command-line "
                "credentials are visible in the process list and shell history; prefer "
                "--cred-file."
            )
        ),
    ] = None,
    cred_file: Annotated[
        str | None, typer.Option(help="Path to a file of provided credentials.")
    ] = None,
    max_steps: Annotated[int | None, typer.Option(help="Maximum agent steps.")] = None,
    unlimited: Annotated[bool, typer.Option("--unlimited", help="No step cap.")] = False,
    max_time: Annotated[int | None, typer.Option(help="Wall-clock limit in minutes.")] = None,
    model: Annotated[str | None, typer.Option(help="Override the model.")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", help="Reduce narration.")] = False,
    plain: Annotated[bool, typer.Option("--plain", help="Line-oriented output.")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    unattended: Annotated[
        bool, typer.Option("--unattended", help="Disable interactive prompts.")
    ] = False,
    reset_playbooks: Annotated[
        bool, typer.Option("--reset-playbooks", help="Restore default playbooks.")
    ] = False,
) -> None:
    """Run an autonomous engagement against an authorized target."""
    _not_implemented("run", "Phase 6")


@app.command()
def resume(
    project: Annotated[str, typer.Option(help="Project name to resume.")],
    fresh: Annotated[bool, typer.Option("--fresh", help="Ignore prior history.")] = False,
    refresh_environment: Annotated[
        bool, typer.Option("--refresh-environment", help="Re-profile the host.")
    ] = False,
) -> None:
    """Continue the latest unfinished run for a project."""
    _not_implemented("resume", "Phase 6")


@app.command()
def runs(
    project: Annotated[str, typer.Option(help="Project name.")],
) -> None:
    """List stored runs for a project."""
    _not_implemented("runs", "Phase 6")


@app.command()
def show(
    run_id: Annotated[str, typer.Argument(help="Run id to inspect.")],
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """Inspect the steps and findings of a run."""
    _not_implemented("show", "Phase 6")


@app.command()
def steer(
    project: Annotated[str, typer.Argument(help="Project name.")],
    text: Annotated[str, typer.Argument(help="Directive to append to guidance.md.")],
) -> None:
    """Append a steering directive to a project's guidance.md."""
    _not_implemented("steer", "Phase 4")


@app.command()
def export(
    project: Annotated[str, typer.Argument(help="Project name.")],
    md: Annotated[bool, typer.Option("--md", help="Render Markdown instead of JSONL.")] = False,
    out: Annotated[str | None, typer.Option(help="Write to a file instead of stdout.")] = None,
    run_id: Annotated[str | None, typer.Option("--run", help="Export a single run.")] = None,
) -> None:
    """Render a project's event log from the database."""
    _not_implemented("export", "Phase 3")


@app.command()
def doctor() -> None:
    """Check host tool availability and print install hints."""
    _not_implemented("doctor", "Phase 2")


if __name__ == "__main__":  # pragma: no cover
    app()
