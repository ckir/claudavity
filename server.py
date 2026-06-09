import asyncio
import json
import uuid
import os
from mcp.server.stdio import stdio_server
from mcp.server import Server
import mcp.types as types
from google.antigravity import Agent, LocalAgentConfig

from telemetry import init_db, log_start, log_completion
from isolation import create_worktree, cleanup_worktree

server = Server("agy-mcp-bridge")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="delegate_to_antigravity",
            description="Delegates a codebase modification task to the Antigravity background daemon.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_prompt": {
                        "type": "string",
                        "description": "The strict instruction for the sub-agent."
                    },
                    "target_dir": {
                        "type": "string",
                        "description": "The absolute path to the project workspace."
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Dynamic circuit breaker limit (default 120s).",
                        "default": 120
                    }
                },
                "required": ["task_prompt", "target_dir"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if name != "delegate_to_antigravity":
        raise ValueError(f"Unknown tool: {name}")

    if not arguments:
        raise ValueError("Missing arguments")

    task_prompt = arguments.get("task_prompt")
    target_dir = arguments.get("target_dir")
    timeout_seconds = arguments.get("timeout_seconds", 120)
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())[:8]

    # Initialize DB
    await init_db(target_dir)
    await log_start(target_dir, task_id, task_prompt)

    worktree_path = None
    success = False
    result_text = ""
    error_payload = None

    try:
        # Create isolated worktree
        worktree_path = await create_worktree(target_dir, task_id)

        # Inject SKILL path
        skill_path = os.path.join(target_dir, ".agent", "skills", "claude_subagent", "SKILL.md")
        
        config = LocalAgentConfig(
            system_instructions=f"Load SKILL: {skill_path}. Adhere strictly to the JSON output format.",
            working_directory=worktree_path
        )
        
        async with Agent(config) as agy_sub_agent:
            try:
                # Enforce circuit breaker timeout
                response = await asyncio.wait_for(
                    agy_sub_agent.chat(f"Execute: {task_prompt}"),
                    timeout=timeout_seconds
                )
                
                # We assume the agent returned strict JSON as instructed
                result_text = await response.text()
                
                # Check if it's valid JSON
                try:
                    parsed = json.loads(result_text)
                    if parsed.get("status") == "completed":
                        success = True
                except json.JSONDecodeError:
                    # Not valid JSON, task failed
                    error_payload = "Agent did not return valid JSON. Output: " + result_text[:200]
                    
            except asyncio.TimeoutError:
                error_payload = f"Circuit breaker timeout after {timeout_seconds}s."

    except Exception as e:
        error_payload = f"System Error: {str(e)}"
        
    finally:
        # Log completion
        status_str = "success" if success else "failed"
        await log_completion(target_dir, task_id, status_str, tokens_used=0, final_error=error_payload)
        
        # Cleanup worktree
        if worktree_path:
            try:
                await cleanup_worktree(target_dir, task_id, success=success)
            except Exception as e:
                # If cleanup fails (e.g., merge conflict), let the error propagate
                if not error_payload:
                    error_payload = f"Worktree cleanup failed: {str(e)}"
                success = False

    # Return final result to Claude
    if success:
        return [types.TextContent(type="text", text=result_text)]
    else:
        failure_json = {
            "status": "failed",
            "error": error_payload or "Unknown error"
        }
        return [types.TextContent(type="text", text=json.dumps(failure_json))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
