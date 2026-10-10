"""A SQLite-backed bookkeeping sink.

Connects the Phase 2 bookkeeping tools (``note``, ``set_phase``,
``record_finding``, ``consume_directive``) to the store, and mirrors each write
into the event log.
"""

from __future__ import annotations

from avalon.store.db import Store


class StoreSink:
    """Writes bookkeeping state to a run in the store."""

    def __init__(self, store: Store, run_id: int) -> None:
        self._store = store
        self._run_id = run_id

    def add_note(self, content: str, step_id: int | None) -> int:
        note_id = self._store.add_note(self._run_id, content, step_id=step_id)
        self._store.add_event(self._run_id, "note", content)
        return note_id

    def set_phase(self, phase: str) -> None:
        self._store.set_run_phase(self._run_id, phase)
        self._store.add_event(self._run_id, "phase", phase)

    def record_finding(
        self, title: str, detail: str, severity: str, evidence: str | None
    ) -> int:
        finding_id = self._store.add_finding(
            self._run_id, title, detail, severity, evidence=evidence
        )
        self._store.add_event(self._run_id, "finding", f"[{severity}] {title}")
        return finding_id

    def consume_directive(self, directive_id: int) -> bool:
        consumed = self._store.consume_directive(directive_id)
        if consumed:
            self._store.add_event(self._run_id, "directive_consumed", str(directive_id))
        return consumed
