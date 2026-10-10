"""Tests for the tool registry and execution wrapper."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from avalon.tools.registry import Tool, ToolError, ToolRegistry


class EchoInput(BaseModel):
    text: str


async def _echo(params: EchoInput) -> str:
    return params.text


def _registry(**kwargs: object) -> ToolRegistry:
    registry = ToolRegistry(**kwargs)
    registry.register(Tool("echo", "Echo text back.", EchoInput, _echo))
    return registry


async def test_execute_success_with_json_string() -> None:
    result = await _registry().execute("echo", '{"text": "hi"}')
    assert result.ok
    assert result.output == "hi"
    assert result.error is None


async def test_execute_success_with_dict() -> None:
    result = await _registry().execute("echo", {"text": "yo"})
    assert result.ok
    assert result.output == "yo"


async def test_unknown_tool() -> None:
    result = await _registry().execute("nope", {})
    assert not result.ok
    assert "unknown tool" in (result.error or "")


async def test_invalid_arguments() -> None:
    result = await _registry().execute("echo", '{"wrong": 1}')
    assert not result.ok
    assert "invalid arguments" in (result.error or "")


async def test_malformed_json() -> None:
    result = await _registry().execute("echo", "{not json")
    assert not result.ok


async def test_timeout_is_captured() -> None:
    registry = ToolRegistry(timeout=0.01)

    async def slow(params: EchoInput) -> str:
        await asyncio.sleep(1)
        return "done"

    registry.register(Tool("slow", "Slow tool.", EchoInput, slow))
    result = await registry.execute("slow", {"text": "x"})
    assert not result.ok
    assert "timed out" in (result.error or "")


async def test_output_is_truncated() -> None:
    registry = ToolRegistry(max_output_bytes=5)
    registry.register(Tool("echo", "Echo.", EchoInput, _echo))
    result = await registry.execute("echo", {"text": "abcdefghij"})
    assert result.ok
    assert result.truncated
    assert result.output == "abcde"


async def test_tool_error_is_captured() -> None:
    registry = ToolRegistry()

    async def boom(params: EchoInput) -> str:
        raise ToolError("controlled failure")

    registry.register(Tool("boom", "Boom.", EchoInput, boom))
    result = await registry.execute("boom", {"text": "x"})
    assert not result.ok
    assert result.error == "controlled failure"


async def test_generic_exception_is_captured() -> None:
    registry = ToolRegistry()

    async def boom(params: EchoInput) -> str:
        raise ValueError("bad")

    registry.register(Tool("boom", "Boom.", EchoInput, boom))
    result = await registry.execute("boom", {"text": "x"})
    assert not result.ok
    assert "ValueError" in (result.error or "")


def test_duplicate_registration_raises() -> None:
    registry = _registry()
    with pytest.raises(ToolError):
        registry.register(Tool("echo", "Echo.", EchoInput, _echo))


def test_specs_expose_json_schema() -> None:
    specs = _registry().specs()
    assert [spec.name for spec in specs] == ["echo"]
    assert "properties" in specs[0].parameters
    assert "text" in specs[0].parameters["properties"]


def test_decorator_registration() -> None:
    registry = ToolRegistry()

    @registry.tool("echo", "Echo.", EchoInput)
    async def echo(params: EchoInput) -> str:
        return params.text

    assert registry.names() == ["echo"]
