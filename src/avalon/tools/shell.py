"""The generic shell tool.

This is AVALON's escape hatch: it runs an arbitrary command through the host
shell. It executes whatever it is given, by design — the agent is expected to
run real security tooling on the operator's own machine. Scope enforcement is a
separate concern (the out-of-scope guard) and is not applied here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from avalon.tools.exec import DEFAULT_TIMEOUT, run_shell
from avalon.tools.registry import ToolError


class ShellInput(BaseModel):
    """Input for the shell tool."""

    command: str = Field(..., description="The shell command to run on the host.")
    timeout: float | None = Field(
        None, description="Per-command timeout in seconds (default 120)."
    )


async def shell_handler(params: ShellInput) -> str:
    """Run a shell command and return its exit code and combined output."""
    timeout = params.timeout or DEFAULT_TIMEOUT
    result = await run_shell(params.command, timeout=timeout)
    if result.timed_out:
        raise ToolError(f"command timed out after {timeout:g}s: {params.command}")
    return f"exit_code: {result.returncode}\n{result.output}"
