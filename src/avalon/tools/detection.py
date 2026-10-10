"""Host tool detection and install hints.

AVALON runs on the operator's own host (Kali/Linux-friendly). It detects the
external tools it needs and, when one is missing, prints an install hint for the
detected package manager. Missing *required* tools are a hard stop.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

# Tools AVALON expects to be present. Missing ones are a hard stop.
REQUIRED_TOOLS: tuple[str, ...] = ("nmap", "dig", "curl")

# Package name per package manager, per tool.
_PACKAGES: dict[str, dict[str, str]] = {
    "nmap": {"apt": "nmap", "dnf": "nmap", "pacman": "nmap", "zypper": "nmap"},
    "dig": {"apt": "dnsutils", "dnf": "bind-utils", "pacman": "bind", "zypper": "bind-utils"},
    "curl": {"apt": "curl", "dnf": "curl", "pacman": "curl", "zypper": "curl"},
}

_PACKAGE_MANAGERS: tuple[str, ...] = ("apt", "dnf", "pacman", "zypper")


@dataclass
class ToolStatus:
    """Whether a tool is present and where it lives."""

    name: str
    path: str | None

    @property
    def present(self) -> bool:
        return self.path is not None


def detect_package_manager() -> str | None:
    """Return the first available package manager, or None."""
    for manager in _PACKAGE_MANAGERS:
        if shutil.which(manager) is not None:
            return manager
    return None


def detect(names: tuple[str, ...] = REQUIRED_TOOLS) -> list[ToolStatus]:
    """Check which of ``names`` are on PATH."""
    return [ToolStatus(name=name, path=shutil.which(name)) for name in names]


def missing(names: tuple[str, ...] = REQUIRED_TOOLS) -> list[str]:
    """Return the subset of ``names`` that are not on PATH."""
    return [name for name in names if shutil.which(name) is None]


def install_hint(name: str, manager: str | None = None) -> str:
    """Return an install command for a tool, using the detected package manager."""
    manager = manager or detect_package_manager()
    packages = _PACKAGES.get(name, {})
    if manager and manager in packages:
        return f"sudo {manager} install {packages[manager]}"
    if manager:
        return f"sudo {manager} install {name}"
    return f"install '{name}' with your system package manager"
