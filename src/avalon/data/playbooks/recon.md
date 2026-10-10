---
name: Reconnaissance & Threat Modeling
phase: recon
applies_to: [linux, windows, web]
preconditions: scope confirmed
objectives:
  - Map the target's external footprint
  - Identify live hosts, open ports, and running services
  - Fingerprint web servers, frameworks, and applications
  - Note high-value assets worth deeper testing
tools: [nmap, dns, http, shell, note]
next_phase: vuln-analysis
---

# Reconnaissance & Threat Modeling

Gather intelligence about the target and build a picture of how an adversary would see it.
Prefer passive and low-noise techniques first, then active scanning.

## What to do

- Resolve names and enumerate DNS where relevant (`dns`).
- Port-scan the in-scope hosts (`nmap`), starting with a fast top-ports scan before a full one.
- Fingerprint services and versions from the scan output.
- For web targets, fetch the root and common paths (`http`) and note the server, framework,
  and any obvious application.
- Record every host, port, and service you find with `note` so it enters the state summary.

## What to look for

- Unusual or unexpected open ports.
- Outdated service versions (candidates for the next phase).
- Web technologies with known weaknesses.
- Anything that looks like a high-value asset (admin panels, databases, file shares).

## Narration

Explain each scan you run: what it does, why you chose it, and how to read the output.
