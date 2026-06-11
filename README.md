# claudavity — Claude ↔ Antigravity MCP Bridge

A Python [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that lets a
**master agent** (Claude Code / `claude-cli`) delegate a single, well-scoped coding task to a
**headless [Antigravity](https://pypi.org/project/google-antigravity/) sub-agent**, run that work
in an **isolated git worktree**, and get back a clean, deterministic JSON result — merging the
work on success, discarding it on failure.

It is the *automated* replacement for the manual "paste the task into Antigravity, paste the
result back" workflow.

> **Repo note:** the folder may live under a `…/Rust/…` path for historical reasons, but this is a
> pure-Python project.

---

## 🌟 Why this exists

Long-running or iterative agent work (refactors, multi-file edits, debugging loops) tends to bloat
the master agent's context and is flaky to drive over a terminal/PTY. claudavity solves this with a
**delegated-task pattern**:

1. **Context protection** — the master delegates the messy work and waits for one compact JSON object.
2. **True isolation** — every task runs in its own `git worktree` on a throwaway branch. Success →
   merged back. Failure/timeout → worktree and branch destroyed.
3. **Headless stability** — uses the official `google-antigravity` Python SDK directly, bypassing
   pseudo-terminal flakiness.
4. **Guardrails** — a per-task circuit-breaker timeout (default 120s) prevents runaway sub-agents.
5. **Git is the source of truth** — the task outcome is derived from the *committed git diff* in the
   worktree, **not** from the model's self-reported JSON (which agents intermittently truncate). The
   model's text is used only for a best-effort one-line summary.

---

## 🏗️ How it works

```
  ┌────────────────────┐   delegate_to_antigravity(task, target_dir)   ┌──────────────────┐
  │  Master agent      │ ────────────────────────────────────────────▶ │  server.py (MCP) │
  │  (Claude Code/agy) │                                                │  over stdio      │
  └────────────────────┘                                                └────────┬─────────┘
                                                                                  │ 1. git worktree add (throwaway branch)
                                                                                  │ 2. run google-antigravity Agent in the worktree,
                                                                                  │    injecting SKILL.md (JSON output contract)
                                                                                  │ 3. commit the worktree → derive files_changed from git
                                                                                  │ 4. changes present? → merge branch back  (status: completed)
                                                                                  │    no changes / failure / timeout? → discard (status: failed)
                                                                                  ▼
                                                                       returns {"status","summary","files_changed"}
```

- **`server.py`** — the MCP server (stdio transport). Manages worktrees, timeouts, telemetry, and the
  SKILL injection. Exposes one tool: **`delegate_to_antigravity`**.
- **`isolation.py`** — git worktree create / commit / merge-or-discard.
- **`telemetry.py`** — logs every invocation to a per-workspace SQLite DB.
- **`SKILL.md`** — the output contract handed to the sub-agent on every call.

### The output contract

The sub-agent is instructed to end with a single, short JSON object — **two fields only**:

```json
{ "status": "completed" | "failed", "summary": "<one factual sentence>" }
```

`files_changed` is **not** requested from the model — the bridge derives it from
`git show --name-only` on the worktree commit. This is deliberate: agents frequently truncate long
JSON, and tying success to a model-serialized file list made runs flaky. A run is **`completed`**
when the worktree has committed changes and the agent did not explicitly self-report `failed`.

---

## 🚀 Installation

### Prerequisites
- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- **git** (your target workspaces must be git repositories)

### Setup

```bash
git clone <this-repo-url> claudavity
cd claudavity

# Create the venv and install dependencies (mcp, google-antigravity, aiosqlite, pydantic)
uv sync

# (contributors only) install the lefthook/ruff pre-commit hooks
uv run lefthook install
```

### Authentication ⚠️ (the non-obvious part)

The `google-antigravity` **SDK** authenticates with a **Gemini API key** (or Vertex AI / ADC). It
**does NOT reuse the `agy` CLI's OAuth login** (`~/.gemini/oauth_creds.json`). So "logging into
Antigravity" in the CLI does *not* authenticate this bridge — you must provide a key.

1. Get a free key at <https://aistudio.google.com/app/apikey>.
2. Copy the template and paste your key (the `.env` file is gitignored — your key never gets committed):
   ```bash
   cp .env.example .env
   # edit .env and set GEMINI_API_KEY=...
   ```

The bridge loads `GEMINI_API_KEY` from this `.env` at launch (via `uv run --env-file .env`, below),
so the secret stays out of your MCP config files.

### SKILL.md — centralized, no copying needed

`SKILL.md` ships **inside this repo** and the bridge injects it automatically on every delegation.
**You do not copy it into your projects.** It is bridge-exclusive — the master agent never discovers
it as one of its own skills.

To override the contract for a specific workspace, drop a file at
`<target_workspace>/.agent/mcp_bridge/SKILL.md`; the bridge prefers that path if it exists, otherwise
it uses the canonical one in this repo.

---

## 🔌 Registering the bridge

> **Two separate MCP hosts — don't confuse them.** Claude Code and `agy` each read their *own* MCP
> config. Registering in one does **not** make the tool available in the other. For the intended
> design (Claude is the master that calls `delegate_to_antigravity`), register it with **Claude Code**.
> Registering it only in `agy` means "agy delegating to a nested Antigravity".

In every example below, replace `ABS/PATH/TO/claudavity` with the absolute path to your clone. On
Windows, use forward slashes (e.g. `C:/Users/you/Development/claudavity`) and the absolute path to
`uv.exe` (e.g. `C:/Users/you/.local/bin/uv.exe`).

### A) Claude Code (master) — recommended

Use the CLI (no secret stored in the config; the key is read from `.env`):

```bash
claude mcp add agy-mcp-bridge -s user -- \
  uv run --directory ABS/PATH/TO/claudavity --env-file ABS/PATH/TO/claudavity/.env python server.py
```

Then **restart Claude Code** (MCP servers load at session start) and verify:

```bash
claude mcp list          # expect: agy-mcp-bridge ✔ Connected
```

Equivalent manual entry (in `~/.claude.json` user scope, or a project `.mcp.json`):

```json
{
  "mcpServers": {
    "agy-mcp-bridge": {
      "command": "uv",
      "args": [
        "run", "--directory", "ABS/PATH/TO/claudavity",
        "--env-file", "ABS/PATH/TO/claudavity/.env",
        "python", "server.py"
      ]
    }
  }
}
```

### B) antigravity-cli (`agy`)

`agy` reads MCP servers from **`~/.gemini/config/mcp_config.json` ONLY**. It silently **ignores**
`~/.gemini/settings.json` `mcpServers` (that's plain gemini-cli's file) — a misconfigured server
fails silently with no error and no log line. Add:

```json
{
  "mcpServers": {
    "agy-mcp-bridge": {
      "command": "ABS/PATH/TO/uv.exe",
      "args": [
        "run", "--directory", "ABS/PATH/TO/claudavity",
        "--env-file", "ABS/PATH/TO/claudavity/.env",
        "python", "server.py"
      ]
    }
  }
}
```

Then **restart `agy`**. On a successful connect, `agy` writes a per-tool schema cache at
`~/.gemini/antigravity-cli/mcp/agy-mcp-bridge/` — the presence of that folder confirms it loaded
(the `/mcp` UI lists it, somewhat confusingly, under a "Plugins" header).

> **Restart caveat:** both hosts hold `server.py` in memory for the life of the session. After you
> change `server.py`, `isolation.py`, or `SKILL.md`, **restart the host** (Claude Code / `agy`) to
> pick it up. The standalone test clients below always spawn a fresh `server.py`, so they don't need
> a restart.
>
> **Cold start** is ~8s the first time (the `google-antigravity` import is heavy); subsequent calls
> are fast.

---

## 🧪 Testing

Two self-contained clients are included — no external MCP inspector required.

### Real end-to-end test (drives the actual sub-agent)

Requires a valid `GEMINI_API_KEY` in `.env`. It creates a throwaway git repo, runs a real
delegation, verifies the file was created **and merged back**, then cleans up.

```bash
uv run python real_test_client.py
```

Expected tail:

```
==== JSON Result Payload ====
{"status": "completed", "summary": "...", "files_changed": ["hello_from_subagent.txt"]}
=============================
VERIFIED: hello_from_subagent.txt merged into sandbox -> 'It works!\n'
```

### Mock test (no API key, no model call)

Drives the worktree/merge plumbing with a canned response via the `MOCK_AGENT_RESPONSE` env var:

```bash
uv run python test_client.py
```

### Optional: the official MCP Inspector

Because the server uses standard `stdio` transport, the official inspector works directly:

```bash
# Mac/Linux
npx @modelcontextprotocol/inspector \
  uv run --directory ABS/PATH/TO/claudavity --env-file ABS/PATH/TO/claudavity/.env python server.py
```

```powershell
# Windows (PowerShell)
npx @modelcontextprotocol/inspector `
  uv run --directory ABS/PATH/TO/claudavity --env-file ABS/PATH/TO/claudavity/.env python server.py
```

---

## 🛠️ Using the tool

Once registered with your master agent, invoke (or let the agent invoke) **`delegate_to_antigravity`**:

| Argument          | Type    | Required | Description                                          |
| ----------------- | ------- | -------- | ---------------------------------------------------- |
| `task_prompt`     | string  | yes      | The strict, self-contained instruction for the sub-agent. |
| `target_dir`      | string  | yes      | Absolute path to the target **git** workspace.       |
| `timeout_seconds` | integer | no (120) | Circuit-breaker limit; the run fails if exceeded.    |

Returns one JSON object:

```json
{ "status": "completed", "summary": "…", "files_changed": ["relative/path", "…"] }
```

…or on failure:

```json
{ "status": "failed", "error": "…reason (timeout / no changes / explicit failure / system error)…" }
```

**Tips for good results:** keep tasks small and unambiguous; the sub-agent is told to do exactly what
is asked and nothing more (no incidental refactors). If the target repo has uncommitted changes you
want excluded from the sub-agent's view, commit or stash them first — the worktree branches from the
current `HEAD`.

---

## 📊 Telemetry & files on disk

Per target workspace, under `<target_dir>/.agent/` (all gitignored by this repo's `.gitignore`):

- **`telemetry.db`** — SQLite log of every invocation: `task_id`, `prompt`, start/end time, status,
  `tokens_used`, `final_error`.
- **`server.log`** — debug log from the bridge.
- **`worktrees/task-<id>/`** — the transient isolation worktree (removed after each run).

> Add the same three patterns to your *target project's* `.gitignore` so bridge artifacts don't get
> committed there:
> ```
> .agent/telemetry.db
> .agent/worktrees/
> .agent/server.log
> ```

---

## 🩺 Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| Tool not listed in `agy` (no error) | Registered in `settings.json` instead of `~/.gemini/config/mcp_config.json`. Move it; restart `agy`; check for `~/.gemini/antigravity-cli/mcp/agy-mcp-bridge/`. |
| Tool not listed in Claude Code | MCP loads at session start — **restart Claude Code**. Verify with `claude mcp list`. |
| `can't open file 'server.py'` | The process cwd wasn't the repo. Always use `uv run --directory ABS/PATH/TO/claudavity …` (don't rely on relative `args:["server.py"]`). |
| Auth / 401 / "API key" errors | `GEMINI_API_KEY` not loaded. Confirm `.env` exists with a real key and the config uses `--env-file …/.env`. The SDK does **not** use `agy`'s OAuth. |
| `status: failed`, "no committed changes" | The sub-agent didn't modify any files (or the task was a no-op). Check `summary`/`server.log`. |
| Code changes seem ignored | The host cached the old `server.py`. Restart the host (see the restart caveat). |
| Merge conflict on a task | The branch `agy-task-<id>` is preserved for manual review; the merge is aborted so your workspace stays clean. |

---

*Built for local Windows development and headless Linux servers.*
