"""Tests for the OpenRouter adapter, using mocked HTTP (respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from avalon.llm.base import (
    LLMError,
    LLMHTTPError,
    LLMInsufficientCredits,
    Message,
    ToolSpec,
)
from avalon.llm.openrouter import OpenRouterProvider

BASE = "https://openrouter.ai/api/v1"
URL = f"{BASE}/chat/completions"


def _provider(**kwargs: object) -> OpenRouterProvider:
    return OpenRouterProvider("test-key", base_url=BASE, max_retries=2, **kwargs)


def _ok_body(content: str = "hello", model: str = "test/model") -> dict:
    return {
        "model": model,
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("avalon.llm.openrouter.asyncio.sleep", _instant)


@respx.mock
async def test_complete_parses_message_and_usage() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json=_ok_body()))
    provider = _provider()
    completion = await provider.complete([Message(role="user", content="hi")])
    assert completion.message.content == "hello"
    assert completion.message.role == "assistant"
    assert completion.usage.total_tokens == 5
    assert completion.finish_reason == "stop"


@respx.mock
async def test_complete_parses_tool_calls() -> None:
    body = {
        "model": "test/model",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "shell", "arguments": '{"command": "id"}'},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    respx.post(URL).mock(return_value=httpx.Response(200, json=body))
    provider = _provider()
    tools = [ToolSpec(name="shell", description="run", parameters={"type": "object"})]
    completion = await provider.complete([Message(role="user", content="run id")], tools)
    assert len(completion.message.tool_calls) == 1
    call = completion.message.tool_calls[0]
    assert call.name == "shell"
    assert call.arguments == '{"command": "id"}'
    assert completion.finish_reason == "tool_calls"


@respx.mock
async def test_402_uses_backup_model() -> None:
    route = respx.post(URL)
    route.side_effect = [
        httpx.Response(402, json={"error": {"message": "insufficient credits"}}),
        httpx.Response(200, json=_ok_body(model="free/model")),
    ]
    provider = _provider(backup_model="free/model")
    completion = await provider.complete([Message(role="user", content="hi")])
    assert completion.model == "free/model"
    assert route.call_count == 2
    # The second request must target the backup model.
    import json

    second = json.loads(route.calls[1].request.content)
    assert second["model"] == "free/model"


@respx.mock
async def test_402_without_backup_raises() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(402, json={"error": {"message": "insufficient credits"}})
    )
    provider = _provider()
    with pytest.raises(LLMInsufficientCredits):
        await provider.complete([Message(role="user", content="hi")])


@respx.mock
async def test_5xx_is_retried_then_succeeds() -> None:
    route = respx.post(URL)
    route.side_effect = [
        httpx.Response(503, text="unavailable"),
        httpx.Response(200, json=_ok_body()),
    ]
    provider = _provider()
    completion = await provider.complete([Message(role="user", content="hi")])
    assert completion.message.content == "hello"
    assert route.call_count == 2


@respx.mock
async def test_4xx_is_not_retried() -> None:
    route = respx.post(URL)
    route.mock(return_value=httpx.Response(401, json={"error": {"message": "bad key"}}))
    provider = _provider()
    with pytest.raises(LLMHTTPError) as excinfo:
        await provider.complete([Message(role="user", content="hi")])
    assert excinfo.value.status_code == 401
    assert route.call_count == 1


@respx.mock
async def test_stream_yields_text_and_final_completion() -> None:
    sse = (
        'data: {"model": "test/model", "choices": [{"delta": {"content": "Hel"}}]}\n\n'
        'data: {"model": "test/model", "choices": [{"delta": {"content": "lo"}}]}\n\n'
        'data: {"model": "test/model", "choices": [{"delta": {}, "finish_reason": "stop"}],'
        ' "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post(URL).mock(
        return_value=httpx.Response(
            200, content=sse.encode(), headers={"content-type": "text/event-stream"}
        )
    )
    provider = _provider()
    chunks: list[str] = []
    final = None
    async for event in provider.stream([Message(role="user", content="hi")]):
        chunks.append(event.text)
        if event.completion is not None:
            final = event.completion
    assert "".join(chunks) == "Hello"
    assert final is not None
    assert final.message.content == "Hello"
    assert final.usage.total_tokens == 3


@respx.mock
async def test_stream_falls_back_to_non_streaming_on_error() -> None:
    route = respx.post(URL)
    route.side_effect = [
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
        httpx.Response(200, json=_ok_body(content="fallback")),
    ]
    provider = _provider()
    texts: list[str] = []
    final = None
    async for event in provider.stream([Message(role="user", content="hi")]):
        texts.append(event.text)
        if event.completion is not None:
            final = event.completion
    assert final is not None
    assert final.message.content == "fallback"
    assert "fallback" in "".join(texts)


def test_rejects_non_https_base_url() -> None:
    with pytest.raises(ValueError):
        OpenRouterProvider("test-key", base_url="http://openrouter.ai/api/v1")


def test_allows_loopback_http_base_url() -> None:
    provider = OpenRouterProvider("test-key", base_url="http://127.0.0.1:8080/v1")
    assert provider.model


@respx.mock
async def test_response_size_cap_is_enforced() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json=_ok_body(content="x" * 2000)))
    provider = _provider(max_response_bytes=100)
    with pytest.raises(LLMError):
        await provider.complete([Message(role="user", content="hi")])
