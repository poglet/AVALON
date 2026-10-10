# AVALON

**A**utomated **V**ulnerability **A**nalysis and **L**ogical **O**ffensive **N**etwork — an
autonomous, LLM-driven penetration-testing framework.

AVALON runs a fully autonomous Reason → Act → Observe → Refine loop against a target you are
authorized to test, calling real security tools on your own host, storing all state and
evidence in a local SQLite database, and narrating every step in plain English so a user with
basic pentesting/CTF skills can follow along.

> **Status:** v0.1 in development. See [`plans/avalon-v0.1-plan.md`](plans/avalon-v0.1-plan.md)
> for the full design and roadmap.

## ⚠️ Legal & ethical notice

AVALON is a tool for **authorized** security testing only. You must own the target or have
explicit written permission to test it. Running AVALON against systems you do not own or are
not authorized to test is illegal in most jurisdictions. The authors accept no liability for
misuse. This software is provided under the MIT license, without warranty of any kind.

## Requirements

- Python 3.11+
- An [OpenRouter](https://openrouter.ai/) API key
- Security tooling on your host (Kali Linux recommended): `nmap`, `dig`, `curl`, etc.
  AVALON detects missing tools and tells you what to install.

## Install

### 1. Prerequisites

- **Python 3.11 or newer.** Check with `python3 --version`.
- **uv** (recommended) — a fast Python package and tool manager. Install it with:

  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  Then close and reopen your terminal (or run `source $HOME/.local/bin/env`) so `uv` is on your
  `PATH`. Verify with `uv --version`.
- **git** (only needed if you clone the repo rather than downloading a ZIP).

### 2. Get the code

Pick **one** of the two options below.

**Option A — Download the ZIP (no git required)**

1. Open the project's GitHub page in your browser.
2. Click the green **Code** button, then **Download ZIP**.
3. Extract the downloaded ZIP to a folder of your choice. For example, on Linux/macOS:

   ```sh
   mkdir -p ~/avalon
   unzip ~/Downloads/avalon-main.zip -d ~/avalon
   ```

   On Windows, right-click the ZIP and choose **Extract All…**, then pick a folder such as
   `C:\Users\<you>\avalon`.
4. Open a terminal and change into the extracted folder. The folder you want is the one that
   contains `pyproject.toml` and the `src/` directory:

   ```sh
   cd ~/avalon/avalon-main      # Linux/macOS
   cd C:\Users\<you>\avalon\avalon-main   # Windows (PowerShell)
   ```

   Confirm you are in the right place — this should list `pyproject.toml`:

   ```sh
   ls        # macOS/Linux
   dir       # Windows
   ```

**Option B — Clone with git**

```sh
git clone <repo-url> ~/avalon
cd ~/avalon
```

### 3. Install the CLI (production)

From inside the project folder, install AVALON as an isolated command-line tool. This does not
touch the system Python or any other project:

```sh
# recommended: uv installs the CLI into its own tool directory
uv tool install .

# or with pipx
pipx install .

# or with pip, into the active environment
pip install .
```

> Once AVALON is published to PyPI you will also be able to install it by name:
> `uv tool install avalon-core`.

If `avalon` is not found after installing with `uv tool`, run `uv tool update-shell` and reopen
your terminal.

Verify the install:

```sh
avalon --version
```

This places the `avalon` command in your own tool/environment location (for example
`~/.local/share/uv/tools/` for `uv tool`). It does **not** create anything in a project
directory — the `.avalon/` working directory is only created when you first run an engagement.

### 4. Development (contributors)

If you want to modify AVALON, create a project-local virtual environment instead:

```sh
cd ~/avalon
uv sync --extra dev
uv run avalon --version
```

`uv sync` creates `.venv/` inside the project directory and installs `avalon-core` in editable
mode, so your edits to `src/avalon/` take effect immediately. `.venv/` is a local build
artifact — it is gitignored and never part of a release.

## Configure

```sh
cp .env.example .env
# then edit .env and set OPENROUTER_API_KEY
```

Everything else has sensible defaults. Advanced tuning lives in an optional
`.avalon/config.toml`, which is created for you on first run.

## Usage

```sh
# run an autonomous engagement against an authorized target
avalon run --project my-ctf --target 10.10.10.5

# continue the latest unfinished run for a project
avalon resume --project my-ctf

# inspect a run
avalon show <run-id>

# steer a running engagement
avalon steer my-ctf "pivot to the internal web app on 8080"

# export the event log
avalon export my-ctf --md

# check host tooling
avalon doctor
```

## How it works

AVALON follows the **PEX** (Penetration & Exploitation Framework) lifecycle:
`environment → initiation → recon → vuln-analysis → exploitation → post-exploitation →
reporting`. Each phase is driven by an editable Markdown playbook, and the agent narrates
which phase it is in.

State lives in `.avalon/projects/<name>/avalon.db` (SQLite, the single source of truth).
Steering directives live in `.avalon/projects/<name>/guidance.md`.

## Development

```sh
uv run ruff check .
uv run pytest
```

Integration tests are opt-in and target a local OWASP Juice Shop container; they never run in
CI and never touch public hosts:

```sh
uv run pytest -m integration
```

## License

MIT — see [`LICENSE`](LICENSE). Design influences and provenance are documented in
[`docs/PROVENANCE.md`](docs/PROVENANCE.md).
