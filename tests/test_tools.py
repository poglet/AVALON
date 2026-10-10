"""Tests for the built-in tools and host tool detection."""

from __future__ import annotations

import socket

import httpx
import pytest
import respx

from avalon.tools import build_default_registry
from avalon.tools.bookkeeping import InMemorySink
from avalon.tools.detection import detect, install_hint, missing
from avalon.tools.dns import DnsInput, dns_handler
from avalon.tools.exec import CommandResult
from avalon.tools.http import HttpInput, http_handler
from avalon.tools.nmap import NmapInput, nmap_handler
from avalon.tools.registry import ToolError
from avalon.tools.shell import ShellInput, shell_handler

# --- shell -----------------------------------------------------------------


async def test_shell_runs_a_command() -> None:
    output = await shell_handler(ShellInput(command="echo hello-avalon"))
    assert "exit_code: 0" in output
    assert "hello-avalon" in output


async def test_shell_timeout_raises() -> None:
    with pytest.raises(ToolError):
        await shell_handler(ShellInput(command="sleep 5", timeout=0.1))


# --- dns -------------------------------------------------------------------


async def test_dns_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    output = await dns_handler(DnsInput(host="example.test"))
    assert "93.184.216.34" in output


async def test_dns_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(*args: object, **kwargs: object) -> list:
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ToolError):
        await dns_handler(DnsInput(host="nope.invalid"))


# --- http ------------------------------------------------------------------


@respx.mock
async def test_http_fetch() -> None:
    respx.get("http://example.test/").mock(
        return_value=httpx.Response(200, text="hello", headers={"server": "nginx"})
    )
    output = await http_handler(HttpInput(url="http://example.test/"))
    assert "status: 200" in output
    assert "server: nginx" in output
    assert "hello" in output


@respx.mock
async def test_http_error_raises() -> None:
    respx.get("http://example.test/").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(ToolError):
        await http_handler(HttpInput(url="http://example.test/"))


# --- nmap ------------------------------------------------------------------


async def test_nmap_builds_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("avalon.tools.nmap.shutil.which", lambda name: "/usr/bin/nmap")
    captured: dict[str, list[str]] = {}

    async def fake_run_command(args: list[str], *, timeout: float, cwd: str | None = None):
        captured["args"] = args
        return CommandResult(returncode=0, output="scan done")

    monkeypatch.setattr("avalon.tools.nmap.run_command", fake_run_command)
    output = await nmap_handler(NmapInput(target="10.0.0.1", ports="80", extra_args=["-sV"]))
    assert captured["args"] == ["nmap", "-p", "80", "-sV", "10.0.0.1"]
    assert "scan done" in output


async def test_nmap_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("avalon.tools.nmap.shutil.which", lambda name: None)
    with pytest.raises(ToolError):
        await nmap_handler(NmapInput(target="10.0.0.1"))


# --- bookkeeping -----------------------------------------------------------


async def test_bookkeeping_tools_write_to_sink() -> None:
    sink = InMemorySink()
    registry = build_default_registry(sink)

    assert (await registry.execute("note", {"content": "hi"})).ok
    assert sink.notes == [(None, "hi")]

    assert (await registry.execute("set_phase", {"phase": "recon"})).ok
    assert sink.phase == "recon"

    assert (
        await registry.execute(
            "record_finding", {"title": "t", "detail": "d", "severity": "high"}
        )
    ).ok
    assert sink.findings[0][2] == "high"

    assert (await registry.execute("consume_directive", {"directive_id": 1})).ok
    assert 1 in sink.consumed
    # Consuming the same directive twice fails.
    assert not (await registry.execute("consume_directive", {"directive_id": 1})).ok


async def test_set_phase_rejects_unknown_phase() -> None:
    registry = build_default_registry(InMemorySink())
    result = await registry.execute("set_phase", {"phase": "not-a-phase"})
    assert not result.ok


# --- detection -------------------------------------------------------------


def test_detect_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "avalon.tools.detection.shutil.which",
        lambda name: "/usr/bin/nmap" if name == "nmap" else None,
    )
    statuses = detect(("nmap", "dig"))
    assert statuses[0].present
    assert not statuses[1].present
    assert missing(("nmap", "dig")) == ["dig"]


def test_install_hint_uses_package_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "avalon.tools.detection.shutil.which",
        lambda name: "/usr/bin/apt" if name == "apt" else None,
    )
    assert install_hint("dig") == "sudo apt install dnsutils"
