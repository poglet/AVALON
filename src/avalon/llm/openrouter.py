"""OpenRouter adapter implementing the :class:`LLMProvider` interface.

Uses OpenRouter's OpenAI-compatible ``/chat/completions`` endpoint with native
tool calling. Behaviour:

- Non-streaming ``complete()`` supports tool calls.
- ``stream()`` yields text deltas and falls back to non-streaming on error.
- Transient failures (network errors and 5xx) are retried up to ``max_retries``
  times with exponential backoff plus jitter. 4xx responses are never retried.
- On HTTP 402 (insufficient credits) the request is retried once with
  ``backup_model`` if one is configured; otherwise it raises
  :class:`LLMInsufficientCredits` so the caller can stop for a human to top up.

Security notes:

- The API key is only ever sent over HTTPS. A non-HTTPS ``base_url`` is rejected
  unless it points at loopback, so the key cannot be leaked in cleartext.
- Provider responses are read with a hard byte cap to bound memory use from a
  malicious or malfunctioning endpoint.
"""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from avalon.llm.base import (
    Completion,
    LLMConnectionError,
    LLMError,
    LLMHTTPError,
    LLMInsufficientCredits,
    Message,
    StreamEvent,
    ToolCall,
    ToolSpec,
    Usage,
)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024  # 8 MiB
_BACKOFF_BASE = 0.5
_BACKOFF_JITTER = 0.25
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _serialize_message(message: Message) -> dict[str, Any]:
    out: dict[str, Any] = {"role": message.role}
    if message.content is not None:
        out["content"] = message.content
    if message.tool_calls:
        out["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        out["tool_call_id"] = message.tool_call_id
    if message.name is not None:
        out["name"] = message.name
    return out


def _serialize_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _extract_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        return response.text[:500]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)
    if error:
        return str(error)
    return response.text[:500]


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    detail = _extract_error(response)
    if response.status_code == 402:
        raise LLMInsufficientCredits(402, detail)
    raise LLMHTTPError(response.status_code, detail)


def _parse_completion(data: Any, fallback_model: str) -> Completion:
    if not isinstance(data, dict):
        raise LLMError("Provider returned a non-object response")
    choices = data.get("choices") or [{}]
    choice = choices[0] if choices else {}
    if not isinstance(choice, dict):
        raise LLMError("Provider returned a malformed choice")
    raw_message = choice.get("message") or {}
    if not isinstance(raw_message, dict):
        raise LLMError("Provider returned a malformed message")
    tool_calls = [
        ToolCall(
            id=call.get("id", ""),
            name=(call.get("function") or {}).get("name", ""),
            arguments=(call.get("function") or {}).get("arguments") or "",
        )
        for call in (raw_message.get("tool_calls") or [])
        if isinstance(call, dict)
    ]
    message = Message(
        role="assistant",
        content=raw_message.get("content"),
        tool_calls=tool_calls,
    )
    raw_usage = data.get("usage") or {}
    if not isinstance(raw_usage, dict):
        raw_usage = {}
    usage = Usage(
        prompt_tokens=raw_usage.get("prompt_tokens") or 0,
        completion_tokens=raw_usage.get("completion_tokens") or 0,
        total_tokens=raw_usage.get("total_tokens") or 0,
    )
    return Completion(
        message=message,
        model=data.get("model") or fallback_model,
        usage=usage,
        finish_reason=choice.get("finish_reason"),
    )


class OpenRouterProvider:
    """An :class:`LLMProvider` backed by OpenRouter."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        backup_model: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        client: httpx.AsyncClient | None = None,
        app_url: str = "https://github.com/avalon",
        app_title: str = "AVALON",
    ) -> None:
        parsed = httpx.URL(base_url)
        if parsed.scheme != "https" and parsed.host not in _LOOPBACK_HOSTS:
            raise ValueError(
                f"Refusing a non-HTTPS base_url ({base_url!r}): the API key would be "
                "sent in cleartext. Use https:// or a loopback address."
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._backup_model = backup_model
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_response_bytes = max_response_bytes
        self._client = client
        self._owns_client = client is None
        self._app_url = app_url
        self._app_title = app_title

    @property
    def model(self) -> str:
        return self._model

    @property
    def backup_model(self) -> str:
        return self._backup_model

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> OpenRouterProvider:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._app_url,
            "X-Title": self._app_title,
        }

    def _payload(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None,
        model: str,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [_serialize_message(m) for m in messages],
        }
        if tools:
            payload["tools"] = [_serialize_tool(t) for t in tools]
        if stream:
            payload["stream"] = True
        return payload

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = _BACKOFF_BASE * (2**attempt) + random.uniform(0, _BACKOFF_JITTER)
        await asyncio.sleep(delay)

    async def _read_capped(self, response: httpx.Response) -> bytes:
        """Read a response body, refusing to buffer more than the byte cap."""
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > self._max_response_bytes:
                raise LLMError(
                    f"Provider response exceeded the {self._max_response_bytes}-byte cap"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """POST with retries on network errors and 5xx. Returns 4xx responses."""
        client = self._get_client()
        url = f"{self._base_url}/chat/completions"
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with client.stream(
                    "POST", url, headers=self._headers(), json=payload
                ) as response:
                    status = response.status_code
                    # The body is already content-decoded by aiter_bytes(); drop the
                    # encoding/length headers so re-wrapping does not decode twice.
                    headers = {
                        key: value
                        for key, value in response.headers.items()
                        if key.lower()
                        not in {"content-encoding", "content-length", "transfer-encoding"}
                    }
                    body = await self._read_capped(response)
            except httpx.HTTPError as exc:
                last_error = LLMConnectionError(str(exc))
                if attempt < self._max_retries:
                    await self._sleep_backoff(attempt)
                    continue
                raise last_error from exc
            if status >= 500:
                last_error = LLMHTTPError(
                    status, _extract_error(httpx.Response(status, content=body, headers=headers))
                )
                if attempt < self._max_retries:
                    await self._sleep_backoff(attempt)
                    continue
                raise last_error
            return httpx.Response(status, content=body, headers=headers)
        raise last_error or LLMConnectionError("request failed")

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
        *,
        model: str | None = None,
    ) -> Completion:
        chosen = model or self._model
        response = await self._post(self._payload(messages, tools, chosen, stream=False))
        if response.status_code == 402 and self._backup_model:
            response = await self._post(
                self._payload(messages, tools, self._backup_model, stream=False)
            )
            chosen = self._backup_model
        _raise_for_status(response)
        return _parse_completion(response.json(), chosen)

    async def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
        *,
        model: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        chosen = model or self._model
        payload = self._payload(messages, tools, chosen, stream=True)
        yielded = False
        try:
            async for event in self._stream_once(payload, chosen):
                yielded = True
                yield event
            return
        except (LLMHTTPError, LLMConnectionError):
            if yielded:
                raise
        # Fall back to non-streaming (which also handles the 402 backup model).
        completion = await self.complete(messages, tools, model=chosen)
        yield StreamEvent(text=completion.message.content or "", completion=completion)

    async def _stream_once(
        self, payload: dict[str, Any], model: str
    ) -> AsyncIterator[StreamEvent]:
        client = self._get_client()
        url = f"{self._base_url}/chat/completions"
        text_parts: list[str] = []
        finish_reason: str | None = None
        usage = Usage()
        response_model = model
        total_bytes = 0
        try:
            async with client.stream(
                "POST", url, headers=self._headers(), json=payload
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    _raise_for_status(response)
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    # Provider ignored stream=True; parse a normal completion.
                    body = await self._read_capped(response)
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError as exc:
                        raise LLMError("Provider returned malformed JSON") from exc
                    completion = _parse_completion(data, model)
                    yield StreamEvent(
                        text=completion.message.content or "", completion=completion
                    )
                    return
                async for line in response.aiter_lines():
                    total_bytes += len(line)
                    if total_bytes > self._max_response_bytes:
                        raise LLMError(
                            "Provider stream exceeded the "
                            f"{self._max_response_bytes}-byte cap"
                        )
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    if chunk.get("model"):
                        response_model = chunk["model"]
                    raw_usage = chunk.get("usage")
                    if isinstance(raw_usage, dict):
                        usage = Usage(
                            prompt_tokens=raw_usage.get("prompt_tokens") or 0,
                            completion_tokens=raw_usage.get("completion_tokens") or 0,
                            total_tokens=raw_usage.get("total_tokens") or 0,
                        )
                    for choice in chunk.get("choices") or []:
                        if not isinstance(choice, dict):
                            continue
                        delta = choice.get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            text_parts.append(piece)
                            yield StreamEvent(text=piece)
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
        except httpx.HTTPError as exc:
            raise LLMConnectionError(str(exc)) from exc

        message = Message(role="assistant", content="".join(text_parts) or None)
        yield StreamEvent(
            completion=Completion(
                message=message,
                model=response_model,
                usage=usage,
                finish_reason=finish_reason,
            )
        )
