# Implementation Plan: Claude-CLI & Antigravity MCP Bridge

## Phase 1: Project Initialization & Structure
1. Setup Python environment and dependencies (`mcp`, `google-antigravity`, `aiosqlite`, `pydantic`).
2. Scaffold the basic MCP server structure (`server.py`).

## Phase 2: Telemetry & Database
1. Create `telemetry.py` to manage the SQLite connection.
2. Implement schema initialization for the `invocations` table.
3. Create async functions to log start, success, and failure states.

## Phase 3: Workspace Isolation
1. Create `isolation.py` with Git helpers.
2. Implement `create_worktree(target_dir, task_id)` to initialize a safe execution branch.
3. Implement `cleanup_worktree(target_dir, task_id, merge=bool)` to handle merging and deleting the temporary branch.

## Phase 4: Sub-Agent Governance
1. Create the `claude_subagent_protocol.md` SKILL file defining the strict JSON return schema and rules.

## Phase 5: The Core Tool
1. Implement the `delegate_to_antigravity` tool in `server.py`.
2. Wire up the isolation layer, inject the SKILL.md into `LocalAgentConfig`, and execute the daemon.
3. Implement the `asyncio.wait_for` circuit breaker and progressive error extraction.

## Phase 6: Testing & Validation
1. Run the MCP server.
2. Execute a test delegation task to ensure the circuit breaker, isolation, and telemetry work as designed.
