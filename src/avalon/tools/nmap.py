"""The nmap convenience tool.

A typed wrapper over the host's ``nmap`` binary. Arguments are passed as an argv
list (never a shell string), so the target and flags cannot inject shell syntax.
"""

from __future__ import annotations

import shutil

from pydantic import BaseModel, Field

from avalon.tools.exec import run_command
from avalon.tools.registry import ToolError

DEFAULT_TIMEOUT = 300.0


class NmapInput(BaseModel):
    """Input for the nmap tool."""

    target: str = Field(..., description="Host, IP, or CIDR to scan.")
    ports: str | None = Field(None, description="Port spec, e.g. '22,80,443' or '1-1000'.")
    extra_args: list[str] = Field(
        default_factory=list, description="Additional nmap flags, e.g. ['-sV', '-T4']."
    )
    timeout: float | None = Field(None, description="Scan timeout in seconds (default 300).")


async def nmap_handler(params: NmapInput) -> str:
    """Run nmap against a target and return its output."""
    if shutil.which("nmap") is None:
        raise ToolError("nmap is not installed. Install it (e.g. 'sudo apt install nmap').")
    args = ["nmap"]
    if params.ports:
        args += ["-p", params.ports]
    args += params.extra_args
    args.append(params.target)
    result = await run_command(args, timeout=params.timeout or DEFAULT_TIMEOUT)
    if result.timed_out:
        raise ToolError(f"nmap timed out after {params.timeout or DEFAULT_TIMEOUT:g}s")
    return f"exit_code: {result.returncode}\n{result.output}"
