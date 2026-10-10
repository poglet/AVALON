# Provenance & Licensing

AVALON is an independent, clean-room implementation. It is **inspired by** the architectural
ideas of ARTEX and its derivative ScopeWeaver, but **no source code is copied** from either
project.

## Upstream projects reviewed

- **ARTEX** — an autonomous, multi-agent penetration-testing framework.
- **ScopeWeaver** — a derivative reimplementation of ARTEX (reviewed in `scopeweaver-main/`).

Both upstreams are licensed under **AGPL-3.0** and carry strict usage restrictions (local,
isolated research only; no testing of online systems).

## What we took (ideas only)

The following architectural ideas informed AVALON's design. They are concepts, not code:

- A two-graph state model (a global asset graph plus a per-task exploration graph joined by
  anchors) — deferred to milestone M1.
- A Planner / Worker / MainAgent role split — deferred to M2.
- A shared, multi-round todolist for dependency-ordered attack chains — deferred to M2.
- Guard/intercept with rule matching and model-fallback review — deferred to M3.
- Skills packaged as `SKILL.md` files — adopted as a future tool-packaging direction (M7).
- An LLM pool with ordered chains and failover — adopted in spirit via a provider-agnostic
  interface and OpenRouter model routing (M6).
- Layered retries and session headers — adopted as retry/backoff in the provider adapter.
- A recording MITM proxy — deferred to M8.
- The `norma` SDK module shape (agentcore / tool / permission / harness / memory / transcript)
  — mirrored as AVALON's Python module boundaries.

## What we deliberately did not take

- No AGPL-licensed source code, in whole or in part.
- No asset-interception deny lists, command-screening blocklists, or dry-run modes (AVALON
  uses mandatory explicit scope plus a light out-of-scope guard instead).

## AVALON's license

AVALON is licensed under the **MIT License** (see [`../LICENSE`](../LICENSE)), independent of
the AGPL upstreams. This is a deliberate choice: AVALON is a clean-room work and is not a
derivative of ARTEX or ScopeWeaver.

## Safety posture

AVALON is intended for **authorized** security testing only. It requires an explicit target
scope, and it flags out-of-scope hosts/IPs for confirmation before running a command. See the
legal notice in the README.
