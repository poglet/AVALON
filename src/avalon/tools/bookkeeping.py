"""Bookkeeping tools: ``note``, ``set_phase``, ``record_finding``, ``consume_directive``.

These let the agent write structured state (scratchpad notes, phase transitions,
findings, and directive consumption) rather than relying on free text. They write
through a :class:`BookkeepingSink`; Phase 2 ships an in-memory sink, and Phase 3
provides the SQLite-backed one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from avalon.tools.registry import ToolError, ToolRegistry

Phase = Literal[
    "environment",
    "initiation",
    "recon",
    "vuln-analysis",
    "exploitation",
    "post-exploitation",
    "reporting",
]
Severity = Literal["info", "low", "medium", "high", "critical"]

PHASES: tuple[str, ...] = (
    "environment",
    "initiation",
    "recon",
    "vuln-analysis",
    "exploitation",
    "post-exploitation",
    "reporting",
)
SEVERITIES: tuple[str, ...] = ("info", "low", "medium", "high", "critical")


class BookkeepingSink(Protocol):
    """Where bookkeeping tools write their state."""

    def add_note(self, content: str, step_id: int | None) -> int: ...

    def set_phase(self, phase: str) -> None: ...

    def record_finding(
        self, title: str, detail: str, severity: str, evidence: str | None
    ) -> int: ...

    def consume_directive(self, directive_id: int) -> bool: ...


@dataclass
class InMemorySink:
    """A simple in-memory sink, used until the SQLite store exists."""

    notes: list[tuple[int | None, str]] = field(default_factory=list)
    phase: str = "environment"
    findings: list[tuple[str, str, str, str | None]] = field(default_factory=list)
    consumed: set[int] = field(default_factory=set)

    def add_note(self, content: str, step_id: int | None) -> int:
        self.notes.append((step_id, content))
        return len(self.notes)

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def record_finding(
        self, title: str, detail: str, severity: str, evidence: str | None
    ) -> int:
        self.findings.append((title, detail, severity, evidence))
        return len(self.findings)

    def consume_directive(self, directive_id: int) -> bool:
        if directive_id in self.consumed:
            return False
        self.consumed.add(directive_id)
        return True


class NoteInput(BaseModel):
    """Input for the note tool."""

    content: str = Field(..., description="Free-form note to record in the scratchpad.")
    step_id: int | None = Field(None, description="Optional step to attach the note to.")


class SetPhaseInput(BaseModel):
    """Input for the set_phase tool."""

    phase: Phase = Field(..., description="The PEX phase the agent is entering.")


class RecordFindingInput(BaseModel):
    """Input for the record_finding tool."""

    title: str = Field(..., description="Short finding title.")
    detail: str = Field(..., description="What was found and why it matters.")
    severity: Severity = Field(..., description="info, low, medium, high, or critical.")
    evidence: str | None = Field(None, description="Supporting evidence (command/output).")


class ConsumeDirectiveInput(BaseModel):
    """Input for the consume_directive tool."""

    directive_id: int = Field(..., description="Id of the steering directive being acted on.")


def register_bookkeeping_tools(registry: ToolRegistry, sink: BookkeepingSink) -> None:
    """Register the four bookkeeping tools against a sink."""

    @registry.tool(
        "note",
        "Record a free-form note in the run scratchpad (working memory).",
        NoteInput,
        tags=("bookkeeping",),
    )
    async def note(params: NoteInput) -> str:
        note_id = sink.add_note(params.content, params.step_id)
        return f"note recorded (id={note_id})"

    @registry.tool(
        "set_phase",
        "Announce the PEX phase the agent is entering.",
        SetPhaseInput,
        tags=("bookkeeping",),
    )
    async def set_phase(params: SetPhaseInput) -> str:
        sink.set_phase(params.phase)
        return f"phase set to {params.phase}"

    @registry.tool(
        "record_finding",
        "Record a security finding with a severity and optional evidence.",
        RecordFindingInput,
        tags=("bookkeeping",),
    )
    async def record_finding(params: RecordFindingInput) -> str:
        finding_id = sink.record_finding(
            params.title, params.detail, params.severity, params.evidence
        )
        return f"finding recorded (id={finding_id}, severity={params.severity})"

    @registry.tool(
        "consume_directive",
        "Mark a steering directive as acted on so it is no longer surfaced.",
        ConsumeDirectiveInput,
        tags=("bookkeeping",),
    )
    async def consume_directive(params: ConsumeDirectiveInput) -> str:
        if not sink.consume_directive(params.directive_id):
            raise ToolError(f"directive {params.directive_id} is unknown or already consumed")
        return f"directive {params.directive_id} consumed"
