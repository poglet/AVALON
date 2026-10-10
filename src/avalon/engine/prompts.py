"""System prompt assembly: persona, output protocol, playbook, state, guidance."""

from __future__ import annotations

from collections.abc import Sequence

BASE_PERSONA = """\
You are AVALON, an autonomous penetration-testing agent running on the operator's own host.
You work through the PEX lifecycle: environment, initiation, recon, vuln-analysis,
exploitation, post-exploitation, reporting.

You are fully autonomous: keep working until the engagement is complete or you are genuinely
blocked. Narrate as you go, in plain English, so an operator with basic pentesting skills can
follow along. Explain what you are doing, why, what to look for, and what the output means.

Only ever act against the in-scope targets you are given. Never touch anything else."""

OUTPUT_PROTOCOL = """\
How to act:
- To do anything, call a tool. Do not describe an action without taking it.
- Use `shell` for arbitrary commands, and `nmap`, `http`, `dns` for the common cases.
- Use `note` to record working memory, `set_phase` when you move to a new PEX phase,
  `record_finding` for each security finding (with a severity), and `consume_directive` when
  you have acted on an operator directive.
- When the engagement is complete, reply with a final plain-English summary and DO NOT call a
  tool. That ends the run.
- If you are genuinely blocked (a missing credential, an unclear decision, or a repeated
  failure), say so clearly and stop calling tools."""


def build_system_prompt(
    *,
    targets: Sequence[str],
    box_type: str,
    phase: str,
    state_summary: str,
    playbook_body: str | None = None,
    guidance: str | None = None,
) -> str:
    """Assemble the full system prompt for a turn."""
    parts: list[str] = [BASE_PERSONA, OUTPUT_PROTOCOL]
    parts.append(
        f"Engagement: box type is {box_type}. "
        f"In-scope targets: {', '.join(targets) if targets else '(none)'}."
    )
    parts.append(f"Current phase: {phase}.")
    if playbook_body:
        parts.append(f"Phase playbook:\n{playbook_body.strip()}")
    if guidance:
        parts.append(f"Operator guidance (highest priority):\n{guidance.strip()}")
    parts.append(f"Current state:\n{state_summary}")
    return "\n\n".join(parts)
