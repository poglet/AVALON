---
name: Environment Profiling
phase: environment
applies_to: [linux, windows, web]
preconditions: none
objectives:
  - Profile the host AVALON is running on
  - Inventory available tooling and flag anything missing
  - Record network posture so later phases do not rediscover it
tools: [shell]
next_phase: initiation
---

# Environment Profiling

Before touching the target, understand the machine you are operating from. This is a short
phase: gather the facts once, record them, and move on.

## What to gather

- OS, distribution, kernel, and architecture
- CPU, memory, and free disk space
- Current user and privileges (are we root?)
- Network interfaces, IP addresses, routes, gateway, and DNS servers
- Internet connectivity
- Package manager (apt, dnf, pacman, ...)
- Tool inventory: `nmap`, `dig`, `curl`, and any others you expect to need

## How to record it

Use the `shell` tool to run the checks, then record the results with `note` so they appear in
the state summary. Do not spend more than a few steps here — this phase exists to save time
later, not to consume it.

## What to look for

- Missing tools: note them so you can plan around them (or tell the user to install them).
- Privileges: knowing whether you are root changes what is worth attempting.
- Network position: whether you can reach the target directly or need a pivot.
