"""Tests for the engine: messages, playbooks, guidance, environment, ReAct loop."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

from avalon.engine.environment import profile_and_store
from avalon.engine.guidance import append_directive, parse_directives, sync_guidance
from avalon.engine.messages import MessageHistory
from avalon.engine.playbooks import load_playbook, parse_playbook, seed_playbooks
from avalon.engine.react import EngineConfig, ReActEngine
from avalon.llm.base import Completion, Message, ToolCall, ToolSpec
from avalon.store.db import Store
from avalon.store.sink import StoreSink
from avalon.tools import build_default_registry


class FakeProvider:
    """A scripted provider for tests."""

    def __init__(self, script: list[Message], default: Message | None = None) -> None:
        self._script = list(script)
        self._default = default
        self.calls = 0

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
        *,
        model: str | None = None,
    ) -> Completion:
        self.calls += 1
        if self._script:
            message = self._script.pop(0)
        elif self._default is not None:
            message = self._default
        else:
            message = Message(role="assistant", content="done")
        return Completion(message=message, model="fake")

    async def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
        *,
        model: str | None = None,
    ) -> AsyncIterator[object]:
        yield None


def _tool_call(name: str, arguments: dict, call_id: str = "c1") -> Message:
    return Message(
        role="assistant",
        content="thinking",
        tool_calls=[ToolCall(id=call_id, name=name, arguments=json.dumps(arguments))],
    )


def _text(content: str) -> Message:
    return Message(role="assistant", content=content)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "avalon.db")
    store.connect()
    store.migrate()
    yield store
    store.close()


def _run(store: Store) -> int:
    project_id = store.get_or_create_project("demo")
    return store.create_run(project_id, None, model="fake", max_steps=10)


# --- messages --------------------------------------------------------------


def test_message_history() -> None:
    history = MessageHistory("sys")
    history.add_user("hi")
    history.add_assistant("yo", [ToolCall("1", "note", "{}")])
    history.add_tool_result("1", "note", "ok")
    history.set_system("sys2")
    messages = history.messages()
    assert messages[0].content == "sys2"
    assert messages[1].role == "user"
    assert messages[2].tool_calls[0].name == "note"
    assert messages[3].role == "tool"
    assert len(history) == 4


# --- playbooks -------------------------------------------------------------


def test_parse_playbook() -> None:
    text = (
        "---\n"
        "name: Recon\n"
        "phase: recon\n"
        "applies_to: [linux, web]\n"
        "objectives:\n  - map ports\n  - fingerprint\n"
        "tools: [nmap]\n"
        "next_phase: vuln-analysis\n"
        "---\n"
        "# Body\nDo recon."
    )
    playbook = parse_playbook(text)
    assert playbook.phase == "recon"
    assert playbook.applies_to == ["linux", "web"]
    assert playbook.objectives == ["map ports", "fingerprint"]
    assert playbook.next_phase == "vuln-analysis"
    assert "Do recon." in playbook.body


def test_seed_and_load_playbooks(tmp_path: Path) -> None:
    copied = seed_playbooks(tmp_path / "playbooks")
    assert "recon.md" in copied
    playbook = load_playbook("recon", tmp_path / "playbooks")
    assert playbook is not None
    assert playbook.phase == "recon"
    # Re-seeding does not overwrite.
    assert seed_playbooks(tmp_path / "playbooks") == []


# --- guidance --------------------------------------------------------------


def test_parse_directives() -> None:
    text = "# Guidance\n\n- [2026-01-01] pivot to 8080\n- focus on login\nnot a directive\n"
    assert parse_directives(text) == ["pivot to 8080", "focus on login"]


def test_sync_guidance(store: Store, tmp_path: Path) -> None:
    run_id = _run(store)
    guidance = tmp_path / "guidance.md"
    guidance.write_text("- pivot to 8080\n- focus on login\n", encoding="utf-8")
    assert sync_guidance(store, run_id, guidance) == 2
    assert sync_guidance(store, run_id, guidance) == 0
    assert len(store.unconsumed_directives(run_id)) == 2


def test_append_directive(tmp_path: Path) -> None:
    guidance = tmp_path / "guidance.md"
    append_directive(guidance, "pivot to 8080")
    assert "pivot to 8080" in guidance.read_text(encoding="utf-8")


# --- environment -----------------------------------------------------------


def test_profile_and_store(store: Store) -> None:
    run_id = _run(store)
    info = profile_and_store(store, run_id)
    assert "os" in info
    assert store.get_environment(run_id)["os"] == info["os"]


# --- ReAct loop ------------------------------------------------------------


async def test_engine_runs_tool_then_finishes(store: Store) -> None:
    run_id = _run(store)
    registry = build_default_registry(StoreSink(store, run_id))
    provider = FakeProvider([_tool_call("note", {"content": "hi"}), _text("all done")])
    engine = ReActEngine(
        provider, registry, store, run_id, EngineConfig(targets=["10.0.0.1"], max_steps=10)
    )
    status = await engine.run()
    assert status == "finished"
    assert store.list_notes(run_id)[0].content == "hi"
    assert store.get_run(run_id).status == "finished"
    assert len(store.list_steps(run_id)) == 1


async def test_engine_stops_at_max_steps(store: Store) -> None:
    run_id = _run(store)
    registry = build_default_registry(StoreSink(store, run_id))
    provider = FakeProvider([], default=_tool_call("note", {"content": "loop"}))
    engine = ReActEngine(
        provider, registry, store, run_id, EngineConfig(targets=["10.0.0.1"], max_steps=2)
    )
    status = await engine.run()
    assert status == "max_steps"
    assert len(store.list_steps(run_id)) == 2


async def test_engine_blocks_unattended(store: Store) -> None:
    run_id = _run(store)
    registry = build_default_registry(StoreSink(store, run_id))
    provider = FakeProvider([], default=_tool_call("does_not_exist", {}))
    engine = ReActEngine(
        provider,
        registry,
        store,
        run_id,
        EngineConfig(targets=["10.0.0.1"], max_steps=10, unattended=True, blocked_after_failures=2),
    )
    status = await engine.run()
    assert status == "blocked"


async def test_engine_prompts_when_blocked(store: Store) -> None:
    run_id = _run(store)
    registry = build_default_registry(StoreSink(store, run_id))
    provider = FakeProvider(
        [
            _tool_call("does_not_exist", {}, "c1"),
            _tool_call("does_not_exist", {}, "c2"),
            _text("recovered"),
        ]
    )
    prompts: list[str] = []

    def prompt_fn(question: str) -> str:
        prompts.append(question)
        return "try a different approach"

    engine = ReActEngine(
        provider,
        registry,
        store,
        run_id,
        EngineConfig(targets=["10.0.0.1"], max_steps=10, blocked_after_failures=2),
        prompt_fn=prompt_fn,
    )
    status = await engine.run()
    assert status == "finished"
    assert prompts  # the operator was asked
