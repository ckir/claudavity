import asyncio
import logging
import json
import uuid
import os
from mcp.server.stdio import stdio_server
from mcp.server import Server
import mcp.types as types
from google.antigravity import Agent, LocalAgentConfig

from telemetry import init_db, log_start, log_completion
from isolation import create_worktree, cleanup_worktree

# Ensure .agent exists for logging
os.makedirs(".agent", exist_ok=True)
logging.basicConfig(
    filename=".agent/server.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.info("Starting server")

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
                        "description": "The strict instruction for the sub-agent.",
                    },
                    "target_dir": {
                        "type": "string",
                        "description": "The absolute path to the project workspace.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Dynamic circuit breaker limit (default 120s).",
                        "default": 120,
                    },
                },
                "required": ["task_prompt", "target_dir"],
            },
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
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
        logging.info(f"Task {task_id}: Creating worktree")
        # Create isolated worktree
        worktree_path = await create_worktree(target_dir, task_id)
        logging.info(f"Task {task_id}: Worktree created at {worktree_path}")

        # Inject SKILL path
        skill_path = os.path.join(target_dir, ".agent", "mcp_bridge", "SKILL.md")

        mock_response = os.environ.get("MOCK_AGENT_RESPONSE")
        if mock_response:
            logging.info(f"Task {task_id}: Using mock agent response")
            await asyncio.sleep(1)  # Simulate some work
            result_text = mock_response

            try:
                parsed = json.loads(result_text)
                if parsed.get("status") in ["completed", "failed"]:
                    success = True
            except json.JSONDecodeError:
                error_payload = "Mock agent did not return valid JSON."

        else:
            config = LocalAgentConfig(
                system_instructions=f"Load SKILL: {skill_path}. Adhere strictly to the JSON output format.",
                working_directory=worktree_path,
            )

            logging.info(f"Task {task_id}: Instantiating Agent")
            async with Agent(config) as agy_sub_agent:
                try:
                    logging.info(
                        f"Task {task_id}: Agent instantiated, waiting for chat completion"
                    )
                    response = await asyncio.wait_for(
                        agy_sub_agent.chat(f"Execute: {task_prompt}"),
                        timeout=timeout_seconds,
                    )

                    result_text = await response.text()
                    try:
                        parsed = json.loads(result_text)
                        if parsed.get("status") == "completed":
                            success = True
                    except json.JSONDecodeError:
                        error_payload = (
                            "Agent did not return valid JSON. Output: "
                            + result_text[:200]
                        )

                except asyncio.TimeoutError:
                    error_payload = f"Circuit breaker timeout after {timeout_seconds}s."
                    logging.error(f"Task {task_id}: Timeout")

    except Exception as e:
        logging.error(f"Task {task_id}: Exception {str(e)}")
        error_payload = f"System Error: {str(e)}"

    finally:
        logging.info(f"Task {task_id}: Cleanup")
        # Log completion
        status_str = "success" if success else "failed"
        await log_completion(
            target_dir, task_id, status_str, tokens_used=0, final_error=error_payload
        )

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
        failure_json = {"status": "failed", "error": error_payload or "Unknown error"}
        return [types.TextContent(type="text", text=json.dumps(failure_json))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
