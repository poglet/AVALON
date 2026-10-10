"""The SQLite store: connection, migrations, and typed accessors.

The store is the single source of truth for a project. It is synchronous; the
engine calls it from the event loop, which is fine for the small, fast queries
involved.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avalon.store.models import (
    DirectiveRow,
    EventRow,
    FindingRow,
    NoteRow,
    ProjectRow,
    ProvidedAssetRow,
    RunRow,
    StepRow,
    TargetRow,
)
from avalon.store.schema import SCHEMA, SCHEMA_VERSION


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _model(model: type, row: sqlite3.Row | None) -> Any:
    return None if row is None else model(**dict(row))


def _models(model: type, rows: list[sqlite3.Row]) -> list[Any]:
    return [model(**dict(row)) for row in rows]


class Store:
    """A project's SQLite database."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        return self._path

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._conn = conn
        return self._conn

    def migrate(self) -> None:
        conn = self.connect()
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        current = row["v"] if row and row["v"] is not None else 0
        if current < SCHEMA_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, _now()),
            )
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Store:
        self.connect()
        self.migrate()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- projects ----------------------------------------------------------

    def get_or_create_project(self, name: str) -> int:
        conn = self.connect()
        row = conn.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
        if row is not None:
            return int(row["id"])
        cursor = conn.execute(
            "INSERT INTO projects(name, created_at) VALUES (?, ?)", (name, _now())
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def get_project(self, name: str) -> ProjectRow | None:
        row = self.connect().execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        return _model(ProjectRow, row)

    def get_project_by_id(self, project_id: int) -> ProjectRow | None:
        row = self.connect().execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return _model(ProjectRow, row)

    # --- targets -----------------------------------------------------------

    def get_or_create_target(self, project_id: int, scope_spec: str) -> int:
        conn = self.connect()
        row = conn.execute(
            "SELECT id FROM targets WHERE project_id = ? AND scope_spec = ?",
            (project_id, scope_spec),
        ).fetchone()
        if row is not None:
            return int(row["id"])
        cursor = conn.execute(
            "INSERT INTO targets(project_id, scope_spec, created_at) VALUES (?, ?, ?)",
            (project_id, scope_spec, _now()),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def list_targets(self, project_id: int) -> list[TargetRow]:
        rows = self.connect().execute(
            "SELECT * FROM targets WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()
        return _models(TargetRow, rows)

    # --- runs --------------------------------------------------------------

    def create_run(
        self,
        project_id: int,
        target_id: int | None,
        *,
        model: str | None = None,
        max_steps: int | None = None,
    ) -> int:
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO runs(project_id, target_id, started_at, status, model, max_steps, phase) "
            "VALUES (?, ?, ?, 'running', ?, ?, 'environment')",
            (project_id, target_id, _now(), model, max_steps),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def finish_run(self, run_id: int, status: str = "finished") -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE runs SET status = ?, ended_at = ? WHERE id = ?", (status, _now(), run_id)
        )
        conn.commit()

    def get_run(self, run_id: int) -> RunRow | None:
        row = self.connect().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _model(RunRow, row)

    def list_runs(self, project_id: int) -> list[RunRow]:
        rows = self.connect().execute(
            "SELECT * FROM runs WHERE project_id = ? ORDER BY id DESC", (project_id,)
        ).fetchall()
        return _models(RunRow, rows)

    def latest_unfinished_run(self, project_id: int) -> RunRow | None:
        row = self.connect().execute(
            "SELECT * FROM runs WHERE project_id = ? AND status = 'running' "
            "ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        return _model(RunRow, row)

    def set_run_phase(self, run_id: int, phase: str) -> None:
        conn = self.connect()
        conn.execute("UPDATE runs SET phase = ? WHERE id = ?", (phase, run_id))
        conn.commit()

    # --- steps -------------------------------------------------------------

    def add_step(
        self,
        run_id: int,
        idx: int,
        *,
        phase: str | None = None,
        reasoning: str | None = None,
        tool_name: str | None = None,
        command: str | None = None,
        status: str = "running",
    ) -> int:
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO steps(run_id, idx, phase, reasoning, tool_name, command, status, "
            "started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, idx, phase, reasoning, tool_name, command, status, _now()),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def finish_step(self, step_id: int, status: str = "done") -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE steps SET status = ?, ended_at = ? WHERE id = ?", (status, _now(), step_id)
        )
        conn.commit()

    def list_steps(self, run_id: int) -> list[StepRow]:
        rows = self.connect().execute(
            "SELECT * FROM steps WHERE run_id = ? ORDER BY idx", (run_id,)
        ).fetchall()
        return _models(StepRow, rows)

    def add_tool_output(
        self,
        step_id: int,
        stdout: str,
        *,
        stderr: str | None = None,
        truncated: bool = False,
        size: int = 0,
    ) -> int:
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO tool_outputs(step_id, stdout, stderr, truncated, bytes) "
            "VALUES (?, ?, ?, ?, ?)",
            (step_id, stdout, stderr, int(truncated), size),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    # --- findings ----------------------------------------------------------

    def add_finding(
        self,
        run_id: int,
        title: str,
        detail: str,
        severity: str,
        *,
        evidence: str | None = None,
        step_id: int | None = None,
    ) -> int:
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO findings(run_id, step_id, title, detail, severity, evidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, step_id, title, detail, severity, evidence, _now()),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def list_findings(self, run_id: int) -> list[FindingRow]:
        rows = self.connect().execute(
            "SELECT * FROM findings WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        return _models(FindingRow, rows)

    # --- notes -------------------------------------------------------------

    def add_note(self, run_id: int, content: str, *, step_id: int | None = None) -> int:
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO notes(run_id, step_id, content, created_at) VALUES (?, ?, ?, ?)",
            (run_id, step_id, content, _now()),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def list_notes(self, run_id: int) -> list[NoteRow]:
        rows = self.connect().execute(
            "SELECT * FROM notes WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        return _models(NoteRow, rows)

    # --- directives --------------------------------------------------------

    def add_directive(self, run_id: int, content: str, *, source: str = "file") -> int:
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO directives(run_id, ts, content, source) VALUES (?, ?, ?, ?)",
            (run_id, _now(), content, source),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def list_directives(self, run_id: int) -> list[DirectiveRow]:
        rows = self.connect().execute(
            "SELECT * FROM directives WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        return _models(DirectiveRow, rows)

    def unconsumed_directives(self, run_id: int) -> list[DirectiveRow]:
        rows = self.connect().execute(
            "SELECT * FROM directives WHERE run_id = ? AND consumed_at IS NULL ORDER BY id",
            (run_id,),
        ).fetchall()
        return _models(DirectiveRow, rows)

    def consume_directive(self, directive_id: int) -> bool:
        conn = self.connect()
        cursor = conn.execute(
            "UPDATE directives SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL",
            (_now(), directive_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    # --- events ------------------------------------------------------------

    def add_event(self, run_id: int, kind: str, payload: str | None = None) -> int:
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO events(run_id, ts, kind, payload) VALUES (?, ?, ?, ?)",
            (run_id, _now(), kind, payload),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def list_events(self, run_id: int) -> list[EventRow]:
        rows = self.connect().execute(
            "SELECT * FROM events WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        return _models(EventRow, rows)

    # --- environment -------------------------------------------------------

    def set_environment(self, run_id: int, key: str, value: str) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT INTO environment(run_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(run_id, key) DO UPDATE SET value = excluded.value",
            (run_id, key, value),
        )
        conn.commit()

    def get_environment(self, run_id: int) -> dict[str, str]:
        rows = self.connect().execute(
            "SELECT key, value FROM environment WHERE run_id = ? ORDER BY key", (run_id,)
        ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    # --- provided assets ---------------------------------------------------

    def add_provided_asset(
        self, project_id: int, path: str, kind: str, size: int, sha256: str
    ) -> int:
        conn = self.connect()
        conn.execute(
            "INSERT INTO provided_assets(project_id, path, kind, size, sha256, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(project_id, path) DO UPDATE SET kind = excluded.kind, "
            "size = excluded.size, sha256 = excluded.sha256",
            (project_id, path, kind, size, sha256, _now()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM provided_assets WHERE project_id = ? AND path = ?",
            (project_id, path),
        ).fetchone()
        return int(row["id"]) if row else 0

    def list_provided_assets(self, project_id: int) -> list[ProvidedAssetRow]:
        rows = self.connect().execute(
            "SELECT * FROM provided_assets WHERE project_id = ? ORDER BY path", (project_id,)
        ).fetchall()
        return _models(ProvidedAssetRow, rows)
