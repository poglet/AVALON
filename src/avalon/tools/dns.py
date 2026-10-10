"""The DNS lookup convenience tool.

Resolves a hostname to its addresses using the system resolver (no external
binary required). Runs the blocking resolver in a thread so it does not stall
the event loop.
"""

from __future__ import annotations

import asyncio
import socket

from pydantic import BaseModel, Field

from avalon.tools.registry import ToolError


class DnsInput(BaseModel):
    """Input for the DNS lookup tool."""

    host: str = Field(..., description="Hostname to resolve.")


async def dns_handler(params: DnsInput) -> str:
    """Resolve a hostname and return its unique addresses."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(params.host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ToolError(f"could not resolve {params.host}: {exc}") from exc

    addresses: list[str] = []
    for _family, _type, _proto, _canon, sockaddr in infos:
        address = sockaddr[0]
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ToolError(f"no addresses found for {params.host}")
    kind = "IPv6" if ":" in addresses[0] else "IPv4"
    return f"{params.host} -> {', '.join(addresses)} ({kind})"
