"""Project identity and the per-project working directory.

A project is the run identity. Everything for a project lives under
``.avalon/projects/<name>/``: the SQLite database, the steering ``guidance.md``,
optional playbook overrides, and the ``engagement/`` folder for provider-supplied
material.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
AVALON_DIR = ".avalon"

_GUIDANCE_TEMPLATE = """# Guidance

Steering directives for this project. Add one per line, e.g.:

- [ ] pivot to the internal web app on 8080
- [ ] focus on the login flow

`avalon steer <project> "<text>"` appends a timestamped directive here.
"""


class ProjectError(Exception):
    """Raised when a project name is missing or invalid."""


def slugify_target(target: str) -> str:
    """Derive a project slug from a target spec."""
    text = target.strip().lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)  # strip scheme
    text = text.split("/")[0]  # strip path
    text = text.split(":")[0]  # strip port
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "default"


@dataclass
class Project:
    """A resolved project and its on-disk layout."""

    name: str
    root: Path

    @property
    def db_path(self) -> Path:
        return self.root / "avalon.db"

    @property
    def guidance_path(self) -> Path:
        return self.root / "guidance.md"

    @property
    def playbooks_dir(self) -> Path:
        return self.root / "playbooks"

    @property
    def engagement_dir(self) -> Path:
        return self.root / "engagement"

    def ensure(self) -> None:
        """Create the project directory tree and seed guidance.md."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.playbooks_dir.mkdir(exist_ok=True)
        self.engagement_dir.mkdir(exist_ok=True)
        if not self.guidance_path.exists():
            self.guidance_path.write_text(_GUIDANCE_TEMPLATE, encoding="utf-8")


def resolve_project(
    name: str | None,
    targets: list[str] | None = None,
    *,
    base_dir: Path | None = None,
) -> Project:
    """Resolve a project from an explicit name or the first target.

    ``--project`` wins; otherwise a slug is derived from the first target. An
    invalid name is rejected with a clear message.
    """
    if name is None:
        if not targets:
            raise ProjectError("a project name is required (pass --project or --target)")
        name = slugify_target(targets[0])
    if not PROJECT_NAME_RE.match(name):
        raise ProjectError(
            f"invalid project name {name!r}: use lowercase letters, digits, and hyphens "
            "(must start with a letter or digit)"
        )
    base = base_dir or (Path.cwd() / AVALON_DIR / "projects")
    return Project(name=name, root=base / name)
