"""Tool registry and the built-in tools (shell, nmap, http, dns, bookkeeping)."""

from __future__ import annotations

from avalon.tools.bookkeeping import BookkeepingSink, InMemorySink, register_bookkeeping_tools
from avalon.tools.dns import DnsInput, dns_handler
from avalon.tools.http import HttpInput, http_handler
from avalon.tools.nmap import NmapInput, nmap_handler
from avalon.tools.registry import Tool, ToolError, ToolRegistry, ToolResult
from avalon.tools.shell import ShellInput, shell_handler

__all__ = [
    "BookkeepingSink",
    "InMemorySink",
    "Tool",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "build_default_registry",
    "register_bookkeeping_tools",
]


def build_default_registry(sink: BookkeepingSink | None = None) -> ToolRegistry:
    """Build a registry with all built-in tools registered."""
    registry = ToolRegistry()
    registry.register(
        Tool(
            "shell",
            "Run a shell command on the host and return its exit code and output.",
            ShellInput,
            shell_handler,
            ("exec",),
        )
    )
    registry.register(
        Tool(
            "nmap",
            "Scan a target with nmap and return the output.",
            NmapInput,
            nmap_handler,
            ("recon",),
        )
    )
    registry.register(
        Tool(
            "http",
            "Fetch a URL and return status, headers, and a truncated body.",
            HttpInput,
            http_handler,
            ("recon",),
        )
    )
    registry.register(
        Tool(
            "dns",
            "Resolve a hostname to its addresses.",
            DnsInput,
            dns_handler,
            ("recon",),
        )
    )
    register_bookkeeping_tools(registry, sink or InMemorySink())
    return registry
