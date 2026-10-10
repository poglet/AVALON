"""Guidance steering.

The operator steers a run by editing a project's ``guidance.md`` (or via
``avalon steer``). Each step the engine syncs new directive lines into the
``directives`` table and surfaces the unconsumed ones in the state summary. The
agent marks a directive consumed with the ``consume_directive`` tool.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from avalon.store.db import Store

_DIRECTIVE_RE = re.compile(r"^\s*[-*]\s+(?:\[(?P<ts>[^\]]+)\]\s*)?(?P<text>.+?)\s*$")


def parse_directives(text: str) -> list[str]:
    """Extract directive texts from guidance Markdown (bullet lines)."""
    directives: list[str] = []
    for line in text.splitlines():
        match = _DIRECTIVE_RE.match(line)
        if match:
            directives.append(match.group("text"))
    return directives


def sync_guidance(store: Store, run_id: int, guidance_path: Path | str) -> int:
    """Add any new guidance lines to the run's directives. Returns the count added."""
    path = Path(guidance_path)
    if not path.is_file():
        return 0
    existing = {directive.content for directive in store.list_directives(run_id)}
    added = 0
    for text in parse_directives(path.read_text(encoding="utf-8")):
        if text not in existing:
            store.add_directive(run_id, text, source="file")
            existing.add(text)
            added += 1
    return added


def append_directive(guidance_path: Path | str, text: str) -> None:
    """Append a timestamped directive to guidance.md."""
    path = Path(guidance_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"- [{timestamp}] {text}\n")


def guidance_text(store: Store, run_id: int) -> str:
    """Render the unconsumed directives for the system prompt."""
    directives = store.unconsumed_directives(run_id)
    return "\n".join(f"- [{d.id}] {d.content}" for d in directives)
