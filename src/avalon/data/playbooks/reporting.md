---
name: Reporting & Continuous Improvement
phase: reporting
applies_to: [linux, windows, web]
preconditions: testing complete
objectives:
  - Summarise what was tested and what was found
  - Present findings with severity and evidence
  - Suggest remediation and root causes
tools: [note]
next_phase: null
---

# Reporting & Continuous Improvement

Close out the engagement. In v0.1 this phase produces a concise summary from the database;
the full dual Owner/Hunter report generator is a later milestone.

## What to do

- Summarise the engagement: targets, phases reached, and steps used.
- List the findings by severity, each with its evidence.
- Note anything that could not be tested and why.
- Suggest remediation for each finding and, where possible, the underlying root cause.

## How to record it

Write the summary with `note`. The full event log and findings can be exported with
`avalon export <project> --md`.
