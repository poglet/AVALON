"""Subprocess helpers for tools.

Two entry points:

- :func:`run_command` runs an argv list directly (no shell), which is the safe
  way to invoke a known binary such as ``nmap``.
- :func:`run_shell` runs a command string through the host shell. This is the
  generic escape hatch and executes arbitrary commands by design; callers are
  responsible for scope enforcement.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

DEFAULT_TIMEOUT = 120.0


@dataclass
class CommandResult:
    """The result of running a subprocess."""

    returncode: int
    output: str
    timed_out: bool = False


async def _communicate(proc: asyncio.subprocess.Process, timeout: float) -> CommandResult:
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return CommandResult(returncode=-1, output="", timed_out=True)
    return CommandResult(
        returncode=proc.returncode if proc.returncode is not None else -1,
        output=stdout.decode("utf-8", errors="replace"),
    )


async def run_command(
    args: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    cwd: str | None = None,
) -> CommandResult:
    """Run an argv list directly, without a shell."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )
    return await _communicate(proc, timeout)


async def run_shell(
    command: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    cwd: str | None = None,
) -> CommandResult:
    """Run a command string through the host shell."""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )
    return await _communicate(proc, timeout)
