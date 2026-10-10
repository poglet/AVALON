---
name: Initiation & Strategy
phase: initiation
applies_to: [linux, windows, web]
preconditions: environment profiled
objectives:
  - Confirm the engagement scope and rules of engagement
  - Establish the box type (black / grey / white)
  - Note any provided credentials, assets, or documentation
tools: [note]
next_phase: recon
---

# Initiation & Strategy

This is the governance phase. In AVALON most of it is already satisfied by the command line:
the target scope comes from `--target`, the box type from `--box-type`, and any provided
material from `--cred` / `--cred-file` and the project's `engagement/` folder.

## What to confirm

- The in-scope targets (from the state summary).
- The box type: black (no prior knowledge), grey (some), or white (full access/credentials).
- Any credentials or assets provided by the engagement owner.

## How to record it

Summarise the engagement in a `note` so it is visible in the state summary for the rest of the
run. Do not attempt any target interaction in this phase.
