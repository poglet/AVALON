"""State-driven context summary.

Each turn the engine sends a compact summary built from the store — current
phase, environment highlights, findings, the scratchpad, open directives, and
only the last few steps — rather than replaying the whole transcript. Older
detail stays queryable in the database.
"""

from __future__ import annotations

from avalon.store.db import Store

DEFAULT_RECENT_STEPS = 5
_MAX_FINDINGS = 10
_MAX_NOTES = 5
_SNIPPET = 120


def _snippet(text: str | None) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= _SNIPPET else text[: _SNIPPET - 1] + "…"


def build_state_summary(
    store: Store, run_id: int, *, recent_steps: int = DEFAULT_RECENT_STEPS
) -> str:
    """Build a compact, human-readable state summary for a run."""
    run = store.get_run(run_id)
    if run is None:
        return "No run state available."

    lines: list[str] = [f"Phase: {run.phase or 'unknown'}", f"Status: {run.status}"]

    steps = store.list_steps(run_id)
    if run.max_steps:
        lines.append(f"Steps used: {len(steps)} / {run.max_steps}")

    environment = store.get_environment(run_id)
    if environment:
        lines.append("Environment:")
        lines.extend(f"  - {key}: {value}" for key, value in environment.items())

    findings = store.list_findings(run_id)
    if findings:
        lines.append(f"Findings ({len(findings)}):")
        lines.extend(
            f"  - [{finding.severity}] {finding.title}" for finding in findings[-_MAX_FINDINGS:]
        )

    notes = store.list_notes(run_id)
    if notes:
        lines.append("Scratchpad:")
        lines.extend(f"  - {_snippet(note.content)}" for note in notes[-_MAX_NOTES:])

    directives = store.unconsumed_directives(run_id)
    if directives:
        lines.append("Open directives:")
        lines.extend(f"  - [{d.id}] {_snippet(d.content)}" for d in directives)

    if steps:
        lines.append(f"Recent steps (last {recent_steps}):")
        for step in steps[-recent_steps:]:
            detail = _snippet(step.command or step.reasoning)
            lines.append(f"  - #{step.idx} {step.tool_name or 'reason'}: {detail}")

    return "\n".join(lines)
