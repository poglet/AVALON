"""SQLite schema for the AVALON store.

The database is the single source of truth for a project: state, evidence, the
event log, and the engagement index all live here.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS targets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    scope_spec TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (project_id, scope_spec)
);

CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    target_id  INTEGER REFERENCES targets(id),
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    status     TEXT NOT NULL DEFAULT 'running',
    model      TEXT,
    max_steps  INTEGER,
    phase      TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    idx        INTEGER NOT NULL,
    phase      TEXT,
    reasoning  TEXT,
    tool_name  TEXT,
    command    TEXT,
    status     TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    ended_at   TEXT
);

CREATE TABLE IF NOT EXISTS tool_outputs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id   INTEGER NOT NULL REFERENCES steps(id),
    stdout    TEXT,
    stderr    TEXT,
    truncated INTEGER NOT NULL DEFAULT 0,
    bytes     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS findings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    step_id    INTEGER REFERENCES steps(id),
    title      TEXT NOT NULL,
    detail     TEXT,
    severity   TEXT NOT NULL,
    evidence   TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    step_id    INTEGER REFERENCES steps(id),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS directives (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    ts          TEXT NOT NULL,
    content     TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'file',
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  INTEGER NOT NULL REFERENCES runs(id),
    ts      TEXT NOT NULL,
    kind    TEXT NOT NULL,
    payload TEXT
);

CREATE TABLE IF NOT EXISTS environment (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    key    TEXT NOT NULL,
    value  TEXT,
    UNIQUE (run_id, key)
);

CREATE TABLE IF NOT EXISTS provided_assets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    path       TEXT NOT NULL,
    kind       TEXT NOT NULL,
    size       INTEGER NOT NULL,
    sha256     TEXT NOT NULL,
    added_at   TEXT NOT NULL,
    UNIQUE (project_id, path)
);

CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id);
CREATE INDEX IF NOT EXISTS idx_steps_run ON steps(run_id);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id);
CREATE INDEX IF NOT EXISTS idx_notes_run ON notes(run_id);
CREATE INDEX IF NOT EXISTS idx_directives_run ON directives(run_id);
"""
