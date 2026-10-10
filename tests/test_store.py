"""Tests for the SQLite store, engagement indexing, and the store sink."""

from __future__ import annotations

from pathlib import Path

import pytest

from avalon.store.assets import classify, index_engagement, sha256_file
from avalon.store.db import Store
from avalon.store.sink import StoreSink


@pytest.fixture
def store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "avalon.db")
    store.connect()
    store.migrate()
    yield store
    store.close()


def _run(store: Store) -> tuple[int, int]:
    project_id = store.get_or_create_project("demo")
    target_id = store.get_or_create_target(project_id, "10.0.0.1")
    run_id = store.create_run(project_id, target_id, model="m", max_steps=40)
    return project_id, run_id


def test_project_and_target_are_idempotent(store: Store) -> None:
    project_id = store.get_or_create_project("demo")
    assert store.get_or_create_project("demo") == project_id
    target_id = store.get_or_create_target(project_id, "10.0.0.1")
    assert store.get_or_create_target(project_id, "10.0.0.1") == target_id
    assert store.get_project("demo").name == "demo"
    assert store.get_project_by_id(project_id).id == project_id
    assert len(store.list_targets(project_id)) == 1


def test_run_lifecycle_and_resume(store: Store) -> None:
    project_id, run_id = _run(store)
    run = store.get_run(run_id)
    assert run is not None
    assert run.status == "running"
    assert run.phase == "environment"
    assert store.latest_unfinished_run(project_id).id == run_id

    store.set_run_phase(run_id, "recon")
    assert store.get_run(run_id).phase == "recon"

    store.finish_run(run_id)
    assert store.get_run(run_id).status == "finished"
    assert store.latest_unfinished_run(project_id) is None
    assert len(store.list_runs(project_id)) == 1


def test_steps_and_tool_outputs(store: Store) -> None:
    _, run_id = _run(store)
    step_id = store.add_step(run_id, 0, phase="recon", tool_name="shell", command="id")
    store.add_tool_output(step_id, "uid=0", truncated=False, size=5)
    store.finish_step(step_id)
    steps = store.list_steps(run_id)
    assert len(steps) == 1
    assert steps[0].tool_name == "shell"
    assert steps[0].status == "done"


def test_findings_notes_events(store: Store) -> None:
    _, run_id = _run(store)
    store.add_finding(run_id, "SQLi", "injectable param", "high", evidence="' OR 1=1")
    store.add_note(run_id, "remember the admin path")
    store.add_event(run_id, "phase", "recon")
    assert store.list_findings(run_id)[0].severity == "high"
    assert store.list_notes(run_id)[0].content == "remember the admin path"
    assert store.list_events(run_id)[0].kind == "phase"


def test_directives_consume(store: Store) -> None:
    _, run_id = _run(store)
    directive_id = store.add_directive(run_id, "pivot to 8080")
    assert len(store.unconsumed_directives(run_id)) == 1
    assert store.consume_directive(directive_id) is True
    assert store.consume_directive(directive_id) is False
    assert store.unconsumed_directives(run_id) == []


def test_environment_upsert(store: Store) -> None:
    _, run_id = _run(store)
    store.set_environment(run_id, "os", "linux")
    store.set_environment(run_id, "os", "kali")
    assert store.get_environment(run_id) == {"os": "kali"}


def test_store_sink_writes_and_logs(store: Store) -> None:
    _, run_id = _run(store)
    sink = StoreSink(store, run_id)
    sink.add_note("hello", None)
    sink.set_phase("recon")
    sink.record_finding("t", "d", "low", None)
    directive_id = store.add_directive(run_id, "steer")
    assert sink.consume_directive(directive_id) is True

    assert store.get_run(run_id).phase == "recon"
    assert store.list_notes(run_id)[0].content == "hello"
    assert store.list_findings(run_id)[0].title == "t"
    kinds = [event.kind for event in store.list_events(run_id)]
    assert "note" in kinds and "phase" in kinds and "finding" in kinds


def test_classify_and_sha256(tmp_path: Path) -> None:
    assert classify(Path("creds.txt")) == "credential"
    assert classify(Path("server.pem")) == "key"
    assert classify(Path("ca.crt")) == "cert"
    assert classify(Path("notes.md")) == "doc"
    assert classify(Path("blob.bin")) == "other"

    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    assert len(sha256_file(sample)) == 64


def test_index_engagement(store: Store, tmp_path: Path) -> None:
    project_id = store.get_or_create_project("demo")
    engagement = tmp_path / "engagement"
    engagement.mkdir()
    (engagement / "creds.txt").write_text("user:pass", encoding="utf-8")
    (engagement / "server.pem").write_text("key", encoding="utf-8")
    (engagement / "notes.md").write_text("hi", encoding="utf-8")

    assets = index_engagement(store, project_id, engagement)
    kinds = {asset.path: asset.kind for asset in assets}
    assert kinds["creds.txt"] == "credential"
    assert kinds["server.pem"] == "key"
    assert kinds["notes.md"] == "doc"
    assert all(len(asset.sha256) == 64 for asset in assets)


def test_index_engagement_skips_symlinks(store: Store, tmp_path: Path) -> None:
    project_id = store.get_or_create_project("demo")
    engagement = tmp_path / "engagement"
    engagement.mkdir()
    real = tmp_path / "outside.txt"
    real.write_text("secret", encoding="utf-8")
    (engagement / "link.txt").symlink_to(real)

    assets = index_engagement(store, project_id, engagement)
    assert assets == []
