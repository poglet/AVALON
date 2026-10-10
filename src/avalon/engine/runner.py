"""Orchestration for a single engagement run.

Wires the project, store, tools, provider, and engine together. The CLI calls
:func:`run_engagement`; tests can call it with a fake provider.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from avalon.config import get_api_key, load_settings
from avalon.engine.environment import profile_and_store
from avalon.engine.playbooks import seed_playbooks
from avalon.engine.react import EngineConfig, ReActEngine, StepEvent
from avalon.llm.base import LLMProvider
from avalon.llm.openrouter import OpenRouterProvider
from avalon.project import resolve_project
from avalon.store.assets import index_engagement
from avalon.store.db import Store
from avalon.store.sink import StoreSink
from avalon.tools import build_default_registry


@dataclass
class RunResult:
    """The outcome of a run."""

    run_id: int
    status: str


async def run_engagement(
    project_name: str | None,
    targets: list[str],
    *,
    box_type: str = "white",
    model: str | None = None,
    max_steps: int | None = 40,
    max_time_minutes: int | None = None,
    unattended: bool = False,
    reset_playbooks: bool = False,
    on_step: Callable[[StepEvent], None] | None = None,
    on_message: Callable[[str], None] | None = None,
    prompt_fn: Callable[[str], str] | None = None,
    base_dir: Path | None = None,
    provider: LLMProvider | None = None,
) -> RunResult:
    """Run an engagement end to end and return the result."""
    project = resolve_project(project_name, targets, base_dir=base_dir)
    project.ensure()
    seed_playbooks(project.playbooks_dir, reset=reset_playbooks)

    settings = load_settings()
    store = Store(project.db_path)
    store.connect()
    store.migrate()
    owns_provider = provider is None
    try:
        project_id = store.get_or_create_project(project.name)
        target_id = store.get_or_create_target(project_id, targets[0]) if targets else None
        run_id = store.create_run(
            project_id, target_id, model=model or settings.model, max_steps=max_steps
        )
        index_engagement(store, project_id, project.engagement_dir)
        profile_and_store(store, run_id)

        registry = build_default_registry(StoreSink(store, run_id))
        if provider is None:
            provider = OpenRouterProvider(
                get_api_key(),
                model=model or settings.model,
                backup_model=settings.backup_model,
            )
        config = EngineConfig(
            targets=targets,
            box_type=box_type,
            max_steps=max_steps,
            max_time_minutes=max_time_minutes,
            unattended=unattended,
            model=model,
            playbooks_dir=project.playbooks_dir,
            guidance_path=project.guidance_path,
        )
        engine = ReActEngine(
            provider,
            registry,
            store,
            run_id,
            config,
            on_step=on_step,
            on_message=on_message,
            prompt_fn=prompt_fn,
        )
        status = await engine.run()
        return RunResult(run_id=run_id, status=status)
    finally:
        if owns_provider and isinstance(provider, OpenRouterProvider):
            await provider.aclose()
        store.close()
