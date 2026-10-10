"""Tests for event-log export and the state-driven context summary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from avalon.engine.context import build_state_summary
from avalon.store.db import Store
from avalon.store.events import export_jsonl, export_markdown


@pytest.fixture
def populated(tmp_path: Path) -> tuple[Store, int, int]:
    store = Store(tmp_path / "avalon.db")
    store.connect()
    store.migrate()
    project_id = store.get_or_create_project("demo")
    target_id = store.get_or_create_target(project_id, "10.0.0.1")
    run_id = store.create_run(project_id, target_id, model="m", max_steps=40)
    store.set_run_phase(run_id, "recon")
    store.add_event(run_id, "phase", "recon")
    store.add_event(run_id, "tool", "nmap -sV 10.0.0.1")
    store.add_finding(run_id, "Open SSH", "port 22 open", "low", evidence="nmap")
    store.add_note(run_id, "check the web app next")
    store.add_directive(run_id, "pivot to 8080")
    store.set_environment(run_id, "os", "kali")
    step_id = store.add_step(run_id, 0, phase="recon", tool_name="nmap", command="nmap -sV")
    store.finish_step(step_id)
    yield store, project_id, run_id
    store.close()


def test_export_jsonl(populated: tuple[Store, int, int]) -> None:
    store, project_id, _ = populated
    text = export_jsonl(store, project_id)
    lines = [line for line in text.splitlines() if line]
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["kind"] == "phase"
    assert first["payload"] == "recon"


def test_export_markdown(populated: tuple[Store, int, int]) -> None:
    store, project_id, _ = populated
    text = export_markdown(store, project_id)
    assert "# AVALON report — demo" in text
    assert "### Findings (1)" in text
    assert "Open SSH" in text
    assert "check the web app next" in text
    assert "Event log (2)" in text


def test_export_single_run(populated: tuple[Store, int, int]) -> None:
    store, project_id, run_id = populated
    text = export_jsonl(store, project_id, run_id)
    assert "phase" in text


def test_state_summary(populated: tuple[Store, int, int]) -> None:
    store, _, run_id = populated
    summary = build_state_summary(store, run_id)
    assert "Phase: recon" in summary
    assert "os: kali" in summary
    assert "[low] Open SSH" in summary
    assert "check the web app next" in summary
    assert "Open directives:" in summary
    assert "pivot to 8080" in summary
    assert "Recent steps" in summary


def test_state_summary_missing_run(tmp_path: Path) -> None:
    store = Store(tmp_path / "avalon.db")
    store.connect()
    store.migrate()
    try:
        assert build_state_summary(store, 999) == "No run state available."
    finally:
        store.close()
