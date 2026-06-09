# Claude-CLI & Antigravity (agy) MCP Bridge

A Python-based Model Context Protocol (MCP) server that acts as a secure, execution-focused bridge between `claude-cli` (the master orchestrator) and a background `google-antigravity` daemon (the execution sub-agent).

## 🌟 Why This Exists

Agentic workflows often suffer when trying to perform long-running or iterative tasks (like compiling, debugging, or deep refactoring). Terminal scraping is unstable across different OSes, and giving an LLM direct shell access often leads to context-window bloat and infinite loops.

This project solves this by introducing a **Delegated Task Pattern**:
1. **Context Protection:** `claude-cli` delegates messy codebase modifications to a background daemon and waits for a clean, deterministic JSON summary.
2. **True Workspace Isolation:** The MCP server automatically spins up a `git worktree`, allowing the sub-agent to work in total isolation. If it succeeds, it merges back cleanly. If it fails, the worktree is destroyed.
3. **Headless Stability:** By utilizing the official `google-antigravity` Python SDK, the bridge communicates natively, completely bypassing pseudo-terminal (PTY) flakiness over SSH or Windows.
4. **Resilience & Guardrails:** Built-in dynamic circuit breakers (e.g., 120s timeout) prevent infinite sub-agent loops, returning "progressive error payloads" back to the master agent so it knows exactly what went wrong.

## 🏗️ Architecture

- **Master Agent (`claude-cli`)**: Manages high-level project logic and user interaction. Calls the `delegate_to_antigravity` MCP tool.
- **MCP Middleware (`server.py`)**: A stateful Python process serving over `stdio` that manages Git worktrees, enforces timeouts, handles token telemetry, and dynamically loads the sub-agent's SKILL protocol.
- **Sub-Agent (`google-antigravity`)**: Operates as a persistent background engine scoped strictly to the target workspace.

## 🚀 Installation

This project uses modern Python standards, managed by [uv](https://docs.astral.sh/uv/).

### Prerequisites
- Python 3.10+
- `uv` package manager installed
- `git` installed and initialized in your target workspaces

### Setup
1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/agy-mcp-bridge.git
   cd agy-mcp-bridge
   ```
2. Sync the dependencies and create a virtual environment using `uv`:
   ```bash
   uv sync
   ```
3. (Optional for Contributors) Install the pre-commit hooks. This project uses `lefthook` and `ruff` to auto-format and lint code on commit:
   ```bash
   uv run lefthook install
   ```
4. **Injecting the SKILL Protocol**: What is `SKILL.md` and why is it needed?
   The `SKILL.md` file contains a set of hardcoded system instructions that govern the background sub-agent. Without it, the sub-agent might respond with conversational text, markdown formatting, or open-ended questions. `SKILL.md` enforces a strict rule: **the sub-agent must only output a deterministic, machine-readable JSON schema**. This protects the master agent from context bloat and ensures the MCP server can predictably parse the task result.
   
   For any target workspace you want the bridge to operate on, you must copy the provided `SKILL.md` from this repository into the target workspace:
   ```bash
   # Inside your target project workspace
   mkdir -p .agent/skills/claude_subagent
   cp /path/to/claudavity/SKILL.md .agent/skills/claude_subagent/SKILL.md
   ```

## 🔌 Registering as an MCP Server

To use this bridge, you must configure your AI CLI (e.g., `claude-cli` or `antigravity-cli`) to load it as an MCP server.

### For `claude-cli` (or Claude Desktop)
Add the following configuration to your MCP settings file (usually `claude_desktop_config.json` or `mcp.json` depending on your CLI wrapper):

```json
{
  "mcpServers": {
    "agy-mcp-bridge": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/claudavity",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

### For `antigravity-cli`
Antigravity discovers MCP servers in its application data directory.
To register it:
1. Create a directory for the server: `~/.gemini/antigravity-cli/mcp/agy-mcp-bridge`
2. In this directory, define your tool schemas and point the execution command to `uv run python server.py` in the `claudavity` directory.

### 🔍 Verifying the Installation

Once configured, restart your CLI and verify the tool is loaded.

**Claude CLI:**
```bash
# Example command depending on your specific CLI tool
/mcp list
```
*(You should see `agy-mcp-bridge` listed with the `delegate_to_antigravity` tool).*

**Antigravity CLI:**
You can ask the agent to list its available tools, or look for the eager tool name:
`mcp_agy-mcp-bridge_delegate_to_antigravity`.

## 🧪 Testing the Integration

You don't need to configure an external MCP inspector to test if the bridge works. A standalone test client is included!

To run a mock delegation task:
```bash
uv run python test_client.py
```
This will:
1. Connect to `server.py` over `stdio`.
2. Send a prompt to create a dummy text file.
3. Spin up an isolated Git worktree (`.agent/worktrees/task-...`).
4. Execute the sub-agent, merge the worktree, and return the final JSON payload.

## 📊 Telemetry & Governance

- **Governance (`SKILL.md`)**: The sub-agent is strictly governed by `.agent/skills/claude_subagent/SKILL.md`. This forces the sub-agent to return a precise JSON schema, suppressing conversational bloat.
- **Metrics (`telemetry.db`)**: Every invocation is logged to a local SQLite database in `.agent/telemetry.db` containing run times, token usage, circuit breaker timeouts, and final statuses.

---
*Built for local Windows development and headless Linux production servers.*
