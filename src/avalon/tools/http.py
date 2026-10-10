"""The HTTP fetch convenience tool.

Fetches a URL with httpx and returns the status, selected headers, and a
truncated body. Redirects are not followed, so a target cannot bounce the
request to an unintended host.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from avalon.tools.registry import ToolError

DEFAULT_TIMEOUT = 30.0
MAX_BODY_CHARS = 20_000


class HttpInput(BaseModel):
    """Input for the HTTP fetch tool."""

    url: str = Field(..., description="Absolute URL to fetch.")
    method: str = Field("GET", description="HTTP method (GET, HEAD, POST, ...).")
    headers: dict[str, str] = Field(default_factory=dict, description="Extra request headers.")
    body: str | None = Field(None, description="Optional request body.")
    timeout: float | None = Field(None, description="Request timeout in seconds (default 30).")


async def http_handler(params: HttpInput) -> str:
    """Fetch a URL and return status, headers, and a truncated body."""
    timeout = params.timeout or DEFAULT_TIMEOUT
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
            response = await client.request(
                params.method.upper(),
                params.url,
                headers=params.headers or None,
                content=params.body.encode() if params.body else None,
            )
    except httpx.HTTPError as exc:
        raise ToolError(f"request failed: {exc}") from exc

    body = response.text
    truncated = len(body) > MAX_BODY_CHARS
    if truncated:
        body = body[:MAX_BODY_CHARS]
    header_lines = "\n".join(f"{k}: {v}" for k, v in response.headers.items())
    note = "\n[body truncated]" if truncated else ""
    return f"status: {response.status_code}\n{header_lines}\n\n{body}{note}"
