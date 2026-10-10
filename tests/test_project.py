"""Tests for project identity and the working-directory layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from avalon.project import ProjectError, resolve_project, slugify_target


def test_slugify_target() -> None:
    assert slugify_target("10.10.10.5") == "10-10-10-5"
    assert slugify_target("http://Example.COM:8080/path") == "example-com"
    assert slugify_target("10.0.0.0/24") == "10-0-0-0"
    assert slugify_target("!!!") == "default"


def test_resolve_from_target(tmp_path: Path) -> None:
    project = resolve_project(None, ["10.10.10.5"], base_dir=tmp_path)
    assert project.name == "10-10-10-5"
    assert project.root == tmp_path / "10-10-10-5"


def test_resolve_explicit_name(tmp_path: Path) -> None:
    project = resolve_project("my-ctf", base_dir=tmp_path)
    assert project.name == "my-ctf"


def test_invalid_name_rejected(tmp_path: Path) -> None:
    with pytest.raises(ProjectError):
        resolve_project("Bad Name", base_dir=tmp_path)


def test_missing_name_and_target_rejected() -> None:
    with pytest.raises(ProjectError):
        resolve_project(None, [])


def test_ensure_creates_layout(tmp_path: Path) -> None:
    project = resolve_project("demo", base_dir=tmp_path)
    project.ensure()
    assert project.db_path.parent == project.root
    assert project.guidance_path.exists()
    assert project.playbooks_dir.is_dir()
    assert project.engagement_dir.is_dir()
