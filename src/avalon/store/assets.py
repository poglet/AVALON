"""Engagement folder indexing.

Provider-supplied material (credentials, assets, SSL keys, docs) is dropped into
a project's ``engagement/`` folder. AVALON indexes it into ``provided_assets``
(path, kind, size, sha256) so the agent can see what it was given without
dumping file contents into context. Symlinks are skipped.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from avalon.store.db import Store
from avalon.store.models import ProvidedAssetRow

_EXT_KIND: dict[str, str] = {
    ".pem": "key",
    ".key": "key",
    ".p12": "key",
    ".pfx": "key",
    ".crt": "cert",
    ".cer": "cert",
    ".der": "cert",
    ".log": "log",
    ".txt": "doc",
    ".md": "doc",
    ".pdf": "doc",
    ".doc": "doc",
    ".docx": "doc",
    ".json": "doc",
    ".yaml": "doc",
    ".yml": "doc",
    ".csv": "doc",
    ".conf": "doc",
    ".cfg": "doc",
    ".ini": "doc",
}

_NAME_KIND: dict[str, str] = {
    "cred": "credential",
    "password": "credential",
    "passwd": "credential",
    "login": "credential",
    "user": "credential",
}


def classify(path: Path) -> str:
    """Classify a provided asset by name and extension."""
    stem = path.stem.lower()
    for needle, kind in _NAME_KIND.items():
        if needle in stem:
            return kind
    return _EXT_KIND.get(path.suffix.lower(), "other")


def sha256_file(path: Path, *, chunk_size: int = 65536) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def index_engagement(
    store: Store, project_id: int, engagement_dir: Path | str
) -> list[ProvidedAssetRow]:
    """Index every regular file under ``engagement_dir`` into provided_assets."""
    directory = Path(engagement_dir)
    if not directory.is_dir():
        return store.list_provided_assets(project_id)

    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = str(path.relative_to(directory))
        store.add_provided_asset(
            project_id,
            relative,
            classify(path),
            path.stat().st_size,
            sha256_file(path),
        )
    return store.list_provided_assets(project_id)
