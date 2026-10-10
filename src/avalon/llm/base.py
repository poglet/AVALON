"""Provider-agnostic LLM interface and shared message/tool types.

The engine talks only to :class:`LLMProvider`. The OpenRouter adapter is the
only implementation in v0.1, but other providers can be added without touching
the engine.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCall:
    """A tool call requested by the model."""

    id: str
    name: str
    arguments: str  # raw JSON string, as returned by the provider


@dataclass
class Message:
    """A single conversation message."""

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ToolSpec:
    """A tool exposed to the model, with a JSON-schema parameter definition."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class Usage:
    """Token usage reported by the provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class Completion:
    """A completed model response."""

    message: Message
    model: str
    usage: Usage = field(default_factory=Usage)
    finish_reason: str | None = None


@dataclass
class StreamEvent:
    """A streaming event: a text delta and/or the final completion."""

    text: str = ""
    completion: Completion | None = None


class LLMError(Exception):
    """Base class for LLM provider errors."""


class LLMHTTPError(LLMError):
    """An HTTP error returned by the provider."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class LLMInsufficientCredits(LLMHTTPError):
    """HTTP 402 — the account has insufficient credits."""


class LLMConnectionError(LLMError):
    """A network/transport error talking to the provider."""


@runtime_checkable
class LLMProvider(Protocol):
    """The interface the engine depends on."""

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
        *,
        model: str | None = None,
    ) -> Completion:
        """Return a full completion (supports tool calls)."""
        ...

    def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
        *,
        model: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a response, yielding text deltas and a final completion."""
        ...
