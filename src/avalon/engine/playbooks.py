"""Phase playbooks: hybrid Markdown with YAML front matter.

Each playbook is a ``<phase>.md`` file with YAML front matter (name, phase,
applies_to, preconditions, objectives, tools, next_phase) and a Markdown body.
Bundled defaults ship with the package; a project's ``playbooks/`` directory
overrides them and is seeded on first run.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

BUNDLED_PLAYBOOKS = Path(__file__).resolve().parent.parent / "data" / "playbooks"


@dataclass
class Playbook:
    """A parsed phase playbook."""

    name: str
    phase: str
    applies_to: list[str] = field(default_factory=list)
    preconditions: str | None = None
    objectives: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    next_phase: str | None = None
    body: str = ""


def parse_playbook(text: str) -> Playbook:
    """Parse a playbook from its raw text."""
    meta: dict = {}
    body = text
    if text.lstrip().startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2]
    return Playbook(
        name=str(meta.get("name", "")),
        phase=str(meta.get("phase", "")),
        applies_to=list(meta.get("applies_to") or []),
        preconditions=meta.get("preconditions"),
        objectives=list(meta.get("objectives") or []),
        tools=list(meta.get("tools") or []),
        next_phase=meta.get("next_phase"),
        body=body.strip(),
    )


def load_playbook(phase: str, playbooks_dir: Path | None = None) -> Playbook | None:
    """Load a phase playbook, preferring the project copy over the bundled one."""
    candidates: list[Path] = []
    if playbooks_dir is not None:
        candidates.append(Path(playbooks_dir) / f"{phase}.md")
    candidates.append(BUNDLED_PLAYBOOKS / f"{phase}.md")
    for path in candidates:
        if path.is_file():
            return parse_playbook(path.read_text(encoding="utf-8"))
    return None


def seed_playbooks(playbooks_dir: Path | str, *, reset: bool = False) -> list[str]:
    """Copy bundled playbooks into a project directory.

    Existing files are kept unless ``reset`` is true. Returns the names copied.
    """
    directory = Path(playbooks_dir)
    directory.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for source in sorted(BUNDLED_PLAYBOOKS.glob("*.md")):
        destination = directory / source.name
        if reset or not destination.exists():
            shutil.copyfile(source, destination)
            copied.append(source.name)
    return copied
