import os
import asyncio


async def run_git_command(cwd: str, *args) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode(), stderr.decode()


async def create_worktree(target_dir: str, task_id: str) -> str:
    # Check if target is a git repo
    code, _, err = await run_git_command(target_dir, "status")
    if code != 0:
        raise ValueError(
            f"Target directory {target_dir} is not a valid git repository. Error: {err}"
        )

    branch_name = f"agy-task-{task_id}"
    worktree_path = os.path.join(target_dir, ".agent", "worktrees", f"task-{task_id}")

    # Ensure the parent directory exists
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    # Create the branch and worktree
    code, _, err = await run_git_command(
        target_dir, "worktree", "add", worktree_path, "-b", branch_name
    )
    if code != 0:
        raise RuntimeError(f"Failed to create git worktree: {err}")

    return worktree_path


async def cleanup_worktree(target_dir: str, task_id: str, success: bool = False):
    branch_name = f"agy-task-{task_id}"
    worktree_path = os.path.join(target_dir, ".agent", "worktrees", f"task-{task_id}")

    if not os.path.exists(worktree_path):
        return

    # Remove the worktree forcefully
    await run_git_command(target_dir, "worktree", "remove", "-f", worktree_path)

    if success:
        # Merge the changes back to current branch
        code, out, err = await run_git_command(target_dir, "merge", branch_name)
        if code != 0:
            await run_git_command(target_dir, "merge", "--abort")
            raise RuntimeError(
                f"Merge conflict detected. The branch {branch_name} has been preserved for manual review. Git error: {err}"
            )

        # Delete branch after successful merge
        await run_git_command(target_dir, "branch", "-D", branch_name)
    else:
        # If the task failed or timed out, we might want to delete the branch to avoid clutter
        await run_git_command(target_dir, "branch", "-D", branch_name)
