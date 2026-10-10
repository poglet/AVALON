---
name: Vulnerability & Weaponisation Analysis
phase: vuln-analysis
applies_to: [linux, windows, web]
preconditions: recon complete
objectives:
  - Identify vulnerabilities in the discovered services and applications
  - Assess which are realistically exploitable
  - Prepare the specific technique or payload for each candidate
tools: [shell, http, nmap, note, record_finding]
next_phase: exploitation
---

# Vulnerability & Weaponisation Analysis

Move from "what is there" to "what is wrong with it". For each service or application found
during recon, look for weaknesses and decide which are worth exploiting.

## What to do

- Check service versions against known vulnerabilities.
- For web targets, probe for common issues: default credentials, exposed admin panels,
  directory listing, verbose errors, and injection points.
- For each candidate, work out the specific technique you would use to exploit it — do not
  just note "possibly vulnerable".
- Record each confirmed weakness with `record_finding` (title, detail, severity).

## What to look for

- Misconfigurations (default creds, anonymous access, exposed services).
- Outdated software with public exploits.
- Application logic flaws and input-validation weaknesses.

## Narration

Explain the reasoning: why this looks vulnerable, what the impact would be, and how you would
confirm it in the next phase.
