"""Tool registry: declaration, JSON-schema generation, and safe execution.

A tool is a name, a description, a pydantic input model, and an async handler
that takes the validated model and returns a string. The registry derives the
JSON schema the model sees, validates incoming arguments, runs the handler with
a timeout, truncates oversized output, and captures errors as data rather than
exceptions.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from avalon.llm.base import ToolSpec

DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_OUTPUT_BYTES = 64 * 1024


class ToolError(Exception):
    """Raised by a tool handler to signal a controlled failure."""


@dataclass
class ToolResult:
    """The outcome of executing a tool."""

    ok: bool
    output: str = ""
    error: str | None = None
    truncated: bool = False
    duration_ms: int = 0


@dataclass
class Tool:
    """A registered tool."""

    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Any], Awaitable[str]]
    tags: tuple[str, ...] = field(default_factory=tuple)


class ToolRegistry:
    """Holds tools and executes them safely."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._timeout = timeout
        self._max_output_bytes = max_output_bytes

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ToolError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def tool(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        *,
        tags: tuple[str, ...] = (),
    ) -> Callable[[Callable[[Any], Awaitable[str]]], Callable[[Any], Awaitable[str]]]:
        """Decorator that registers an async handler as a tool."""

        def decorator(handler: Callable[[Any], Awaitable[str]]) -> Callable[[Any], Awaitable[str]]:
            self.register(Tool(name, description, input_model, handler, tags))
            return handler

        return decorator

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        """Return the tool specs the model sees."""
        return [
            ToolSpec(
                name=tool.name,
                description=tool.description,
                parameters=tool.input_model.model_json_schema(),
            )
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, arguments: str | dict[str, Any] | None) -> ToolResult:
        """Validate arguments and run a tool, returning a result (never raising)."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool: {name}")

        try:
            raw = _parse_arguments(arguments)
            params = tool.input_model.model_validate(raw)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            return ToolResult(ok=False, error=f"invalid arguments for {name}: {exc}")

        start = time.monotonic()
        try:
            result = tool.handler(params)
            if inspect.isawaitable(result):
                result = await asyncio.wait_for(result, timeout=self._timeout)
            text = result if isinstance(result, str) else str(result)
        except TimeoutError:
            return ToolResult(
                ok=False,
                error=f"tool {name} timed out after {self._timeout:g}s",
                duration_ms=_elapsed_ms(start),
            )
        except ToolError as exc:
            return ToolResult(ok=False, error=str(exc), duration_ms=_elapsed_ms(start))
        except Exception as exc:  # noqa: BLE001 - tool failures are data, not crashes
            return ToolResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=_elapsed_ms(start),
            )

        output, truncated = _truncate(text, self._max_output_bytes)
        return ToolResult(
            ok=True, output=output, truncated=truncated, duration_ms=_elapsed_ms(start)
        )


def _parse_arguments(arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if not arguments.strip():
        return {}
    parsed = json.loads(arguments)
    if not isinstance(parsed, dict):
        raise TypeError("tool arguments must be a JSON object")
    return parsed


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="replace"), True


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
