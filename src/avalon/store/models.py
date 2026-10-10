"""Pydantic row models for the store."""

from __future__ import annotations

from pydantic import BaseModel


class ProjectRow(BaseModel):
    id: int
    name: str
    created_at: str


class TargetRow(BaseModel):
    id: int
    project_id: int
    scope_spec: str
    created_at: str


class RunRow(BaseModel):
    id: int
    project_id: int
    target_id: int | None = None
    started_at: str
    ended_at: str | None = None
    status: str = "running"
    model: str | None = None
    max_steps: int | None = None
    phase: str | None = None


class StepRow(BaseModel):
    id: int
    run_id: int
    idx: int
    phase: str | None = None
    reasoning: str | None = None
    tool_name: str | None = None
    command: str | None = None
    status: str = "running"
    started_at: str
    ended_at: str | None = None


class FindingRow(BaseModel):
    id: int
    run_id: int
    step_id: int | None = None
    title: str
    detail: str | None = None
    severity: str
    evidence: str | None = None
    created_at: str


class NoteRow(BaseModel):
    id: int
    run_id: int
    step_id: int | None = None
    content: str
    created_at: str


class DirectiveRow(BaseModel):
    id: int
    run_id: int
    ts: str
    content: str
    source: str = "file"
    consumed_at: str | None = None


class EventRow(BaseModel):
    id: int
    run_id: int
    ts: str
    kind: str
    payload: str | None = None


class ProvidedAssetRow(BaseModel):
    id: int
    project_id: int
    path: str
    kind: str
    size: int
    sha256: str
    added_at: str
