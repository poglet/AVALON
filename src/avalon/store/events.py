"""Event-log export.

The ``events`` table is the chronological log. JSONL and Markdown transcripts are
rendered from it on demand — there is no separate transcript file at runtime.
"""

from __future__ import annotations

import json

from avalon.store.db import Store
from avalon.store.models import RunRow


def _maybe_json(payload: str | None) -> object:
    if payload is None:
        return None
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return payload


def _runs(store: Store, project_id: int, run_id: int | None) -> list[RunRow]:
    if run_id is not None:
        run = store.get_run(run_id)
        return [run] if run is not None else []
    return store.list_runs(project_id)


def export_jsonl(store: Store, project_id: int, run_id: int | None = None) -> str:
    """Render the event log as JSONL (one event per line)."""
    lines: list[str] = []
    for run in _runs(store, project_id, run_id):
        for event in store.list_events(run.id):
            lines.append(
                json.dumps(
                    {
                        "run_id": run.id,
                        "ts": event.ts,
                        "kind": event.kind,
                        "payload": _maybe_json(event.payload),
                    },
                    ensure_ascii=False,
                )
            )
    return "\n".join(lines) + ("\n" if lines else "")


def export_markdown(store: Store, project_id: int, run_id: int | None = None) -> str:
    """Render a human-readable Markdown report from the store."""
    project = store.get_project_by_id(project_id)
    out: list[str] = [f"# AVALON report — {project.name if project else project_id}", ""]

    for run in _runs(store, project_id, run_id):
        out.append(f"## Run {run.id}")
        out.append("")
        out.append(f"- Status: {run.status}")
        out.append(f"- Phase: {run.phase or 'unknown'}")
        out.append(f"- Model: {run.model or 'default'}")
        out.append(f"- Started: {run.started_at}")
        out.append(f"- Ended: {run.ended_at or 'in progress'}")
        out.append("")

        findings = store.list_findings(run.id)
        out.append(f"### Findings ({len(findings)})")
        out.append("")
        if findings:
            for finding in findings:
                out.append(f"- **[{finding.severity}] {finding.title}** — {finding.detail or ''}")
                if finding.evidence:
                    out.append(f"  - evidence: {finding.evidence}")
        else:
            out.append("_None recorded._")
        out.append("")

        notes = store.list_notes(run.id)
        if notes:
            out.append("### Notes")
            out.append("")
            for note in notes:
                out.append(f"- {note.content}")
            out.append("")

        events = store.list_events(run.id)
        out.append(f"### Event log ({len(events)})")
        out.append("")
        for event in events:
            payload = event.payload or ""
            out.append(f"- `{event.ts}` **{event.kind}** {payload}".rstrip())
        out.append("")

    return "\n".join(out)
