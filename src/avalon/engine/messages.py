"""Message history for the ReAct loop.

Holds the system prompt plus the running conversation. The engine rebuilds the
system prompt each turn (persona + active playbook + state summary + guidance),
so :meth:`MessageHistory.set_system` replaces it in place.
"""

from __future__ import annotations

from collections.abc import Sequence

from avalon.llm.base import Message, ToolCall


class MessageHistory:
    """An ordered list of conversation messages."""

    def __init__(self, system: str = "") -> None:
        self._messages: list[Message] = []
        if system:
            self._messages.append(Message(role="system", content=system))

    def set_system(self, content: str) -> None:
        """Replace the system message (creating it if absent)."""
        if self._messages and self._messages[0].role == "system":
            self._messages[0] = Message(role="system", content=content)
        else:
            self._messages.insert(0, Message(role="system", content=content))

    def add_user(self, content: str) -> None:
        self._messages.append(Message(role="user", content=content))

    def add_assistant(self, content: str | None, tool_calls: Sequence[ToolCall] = ()) -> None:
        self._messages.append(
            Message(role="assistant", content=content, tool_calls=list(tool_calls))
        )

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        self._messages.append(
            Message(role="tool", content=content, tool_call_id=tool_call_id, name=name)
        )

    def messages(self) -> list[Message]:
        return list(self._messages)

    def __len__(self) -> int:
        return len(self._messages)
