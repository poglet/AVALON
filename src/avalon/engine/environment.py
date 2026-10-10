"""Environment phase: profile the host AVALON is running on.

Gathers OS, resources, privileges, network, and tool inventory once per project
and stores it in the ``environment`` table so later phases never rediscover it.
"""

from __future__ import annotations

import getpass
import os
import platform
import socket

from avalon.store.db import Store
from avalon.tools.detection import REQUIRED_TOOLS, detect


def profile_host() -> dict[str, str]:
    """Collect a host profile as key/value pairs."""
    info: dict[str, str] = {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
    }
    try:
        info["user"] = getpass.getuser()
    except (OSError, KeyError):
        info["user"] = "unknown"
    if hasattr(os, "geteuid"):
        info["privileged"] = "yes" if os.geteuid() == 0 else "no"
    for status in detect(REQUIRED_TOOLS):
        info[f"tool:{status.name}"] = status.path or "missing"
    return info


def profile_and_store(store: Store, run_id: int) -> dict[str, str]:
    """Profile the host and persist the result against a run."""
    info = profile_host()
    for key, value in info.items():
        store.set_environment(run_id, key, value)
    store.add_event(run_id, "environment", "profiled host")
    return info
