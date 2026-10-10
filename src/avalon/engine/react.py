"""The autonomous ReAct engine.

Each turn: rebuild the system prompt (persona + active playbook + state summary +
guidance), ask the model, execute any tool calls, record everything, and repeat.
The loop stops when the agent replies without calling a tool (its final summary),
when the step or time cap is reached, when it is blocked, or on a provider error.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from avalon.engine.context import build_state_summary
from avalon.engine.guidance import guidance_text, sync_guidance
from avalon.engine.messages import MessageHistory
from avalon.engine.playbooks import load_playbook
from avalon.engine.prompts import build_system_prompt
from avalon.llm.base import LLMError, LLMInsufficientCredits, LLMProvider, ToolCall
from avalon.store.db import Store
from avalon.tools.registry import ToolRegistry

DEFAULT_MAX_STEPS = 40
DEFAULT_BLOCKED_AFTER = 3


@dataclass
class EngineConfig:
    """Configuration for a run."""

    targets: list[str]
    box_type: str = "white"
    max_steps: int | None = DEFAULT_MAX_STEPS
    max_time_minutes: int | None = None
    unattended: bool = False
    model: str | None = None
    playbooks_dir: Path | None = None
    guidance_path: Path | None = None
    blocked_after_failures: int = DEFAULT_BLOCKED_AFTER


@dataclass
class StepEvent:
    """A single executed step, for rendering."""

    idx: int
    phase: str
    reasoning: str | None
    tool_name: str
    command: str | None
    output: str
    ok: bool
    duration_ms: int = 0


def _command_of(call: ToolCall) -> str | None:
    try:
        arguments = json.loads(call.arguments) if call.arguments else {}
    except json.JSONDecodeError:
        return call.arguments or None
    if isinstance(arguments, dict):
        for key in ("command", "url", "target", "host"):
            if key in arguments:
                return str(arguments[key])
    return call.arguments or None


class ReActEngine:
    """Runs the autonomous loop for a single run."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        store: Store,
        run_id: int,
        config: EngineConfig,
        *,
        on_step: Callable[[StepEvent], None] | None = None,
        on_message: Callable[[str], None] | None = None,
        prompt_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._store = store
        self._run_id = run_id
        self._config = config
        self._on_step = on_step
        self._on_message = on_message
        self._prompt_fn = prompt_fn or input

    def _system_prompt(self) -> str:
        run = self._store.get_run(self._run_id)
        phase = (run.phase if run else None) or "environment"
        playbook = load_playbook(phase, self._config.playbooks_dir)
        return build_system_prompt(
            targets=self._config.targets,
            box_type=self._config.box_type,
            phase=phase,
            state_summary=build_state_summary(self._store, self._run_id),
            playbook_body=playbook.body if playbook else None,
            guidance=guidance_text(self._store, self._run_id) or None,
        )

    async def run(self) -> str:
        """Run the loop to completion and return the final status."""
        history = MessageHistory()
        history.add_user("Begin the engagement. Start with the environment phase.")
        start = time.monotonic()
        step_idx = 0
        consecutive_failures = 0
        status = "finished"

        while True:
            if self._config.max_steps is not None and step_idx >= self._config.max_steps:
                status = "max_steps"
                break
            if self._config.max_time_minutes is not None and (
                (time.monotonic() - start) / 60 >= self._config.max_time_minutes
            ):
                status = "max_time"
                break

            if self._config.guidance_path is not None:
                sync_guidance(self._store, self._run_id, self._config.guidance_path)

            history.set_system(self._system_prompt())
            try:
                completion = await self._provider.complete(
                    history.messages(), self._registry.specs(), model=self._config.model
                )
            except LLMInsufficientCredits:
                status = "insufficient_credits"
                break
            except LLMError as exc:
                status = f"llm_error: {exc}"
                break

            message = completion.message
            history.add_assistant(message.content, message.tool_calls)

            if not message.tool_calls:
                if self._on_message and message.content:
                    self._on_message(message.content)
                self._store.add_event(self._run_id, "final", message.content or "")
                break

            run = self._store.get_run(self._run_id)
            phase = (run.phase if run else None) or "environment"
            for call in message.tool_calls:
                if self._config.max_steps is not None and step_idx >= self._config.max_steps:
                    break
                step_idx += 1
                result = await self._registry.execute(call.name, call.arguments)
                command = _command_of(call)
                step_id = self._store.add_step(
                    self._run_id,
                    step_idx,
                    phase=phase,
                    reasoning=message.content,
                    tool_name=call.name,
                    command=command,
                )
                self._store.add_tool_output(
                    step_id,
                    result.output or result.error or "",
                    truncated=result.truncated,
                    size=len(result.output or ""),
                )
                self._store.finish_step(step_id, "done" if result.ok else "error")
                self._store.add_event(self._run_id, "tool", f"{call.name}: {command or ''}")
                history.add_tool_result(
                    call.id,
                    call.name,
                    result.output if result.ok else f"ERROR: {result.error}",
                )
                if self._on_step:
                    self._on_step(
                        StepEvent(
                            idx=step_idx,
                            phase=phase,
                            reasoning=message.content,
                            tool_name=call.name,
                            command=command,
                            output=result.output or result.error or "",
                            ok=result.ok,
                            duration_ms=result.duration_ms,
                        )
                    )
                consecutive_failures = 0 if result.ok else consecutive_failures + 1

            if consecutive_failures >= self._config.blocked_after_failures:
                if self._config.unattended:
                    status = "blocked"
                    break
                reply = self._prompt_fn(
                    "AVALON is blocked. Provide guidance, or press Enter to stop: "
                )
                if not reply.strip():
                    status = "blocked"
                    break
                history.add_user(reply)
                consecutive_failures = 0

        self._store.finish_run(self._run_id, status)
        self._store.add_event(self._run_id, "run_end", status)
        return status
