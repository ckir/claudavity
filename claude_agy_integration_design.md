# Claude-CLI & Antigravity (agy) MCP Bridge Design

## 1. Understanding Summary
- **What is being built:** A Python-based Model Context Protocol (MCP) server that acts as a secure bridge between `claude-cli` (the master orchestrator) and a background `google-antigravity` daemon (the execution sub-agent).
- **Why it exists:** To eliminate terminal-scraping instability, protect the master agent's context window from noisy iteration loops, and provide a reliable API for safe codebase modifications.
- **Who it is for:** Developers running advanced agentic workflows locally (Windows) or headlessly (Linux over SSH).
- **Key constraints:** The sub-agent must strictly adhere to a deterministic JSON schema output, operate in true workspace isolation, and respect dynamic circuit breakers that return progressive error payloads upon timeout.
- **Explicit non-goals:** The sub-agent will NOT dictate high-level project architecture, nor will it initiate its own external multi-agent sessions. It is strictly a focused execution engine.

## 2. Explicit Assumptions
1. **Framework:** We will use the official Anthropic `mcp` Python SDK for the server middleware.
2. **Telemetry:** The SQLite telemetry database will be stored locally within each target workspace (e.g., `.agent/telemetry.db`) rather than a global app-data folder, keeping metrics isolated per project.
3. **Repository State:** Because we are using Git Worktrees for isolation, we assume the target directory is an initialized Git repository. If it is not, the MCP server should fail fast and alert the master agent.

## 3. Decision Log

| Decision | Chosen Approach | Alternatives Considered | Rationale |
|----------|----------------|-------------------------|-----------|
| **Tool Architecture** | Single Blocking Tool (`delegate_to_antigravity`) | Multi-tool async polling (`start_delegation` + `check_status`) | LLMs lack background event loops. Async polling causes rapid, token-burning spin-loops. Blocking the tool call pauses the LLM securely and costs zero tokens while waiting for the 120s limit. |
| **Workspace Isolation** | Git Worktrees | In-place branching, or Temporary directory copy (`shutil.copytree`) | Git worktrees provide total file isolation without the massive I/O penalty of copying large directories (like `node_modules` or `target`). |
| **Error Handling** | Progressive Error Payloads | Generic timeout error messages | If the sub-agent hits the circuit breaker, returning the *last known error* gives the master agent actionable context to fix the problem, rather than a blind failure. |

## 4. Final Architecture

### The MCP Middleware
The MCP server exposes a single primary tool:
- **`delegate_to_antigravity(task_prompt: str, target_dir: str, timeout_seconds: int = 120)`**

### Execution Flow
1. **Receive:** The MCP server receives the blocking tool call.
2. **Isolate:** It executes `git worktree add .agent/worktrees/task-<id> -b agy-task-<id>`.
3. **Configure:** It initializes `LocalAgentConfig` from the `google-antigravity` SDK, setting the `working_directory` to the worktree and injecting the `claude_subagent_protocol` SKILL.md rules.
4. **Execute:** It invokes the sub-agent asynchronously. During this time, the HTTP/stdio request remains open, blocking Claude.
5. **Resolve:** 
   - **Success:** Parses the JSON response, merges the worktree changes back to the main directory, and returns the JSON to Claude.
   - **Timeout:** Catches `asyncio.TimeoutError`, extracts the last error from the sub-agent logs, and returns a progressive error payload.
6. **Cleanup:** A `finally` block guarantees the git worktree and temporary branch are deleted regardless of the outcome.

### Telemetry Sink
All runs are logged to `.agent/telemetry.db` capturing: `task_id`, `prompt`, `start_time`, `end_time`, `status`, `tokens_used`, and `final_error`.
