"""Task lifecycle tools: claim, progress, complete, block, handoff, next."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agendum.env_context import get_device_name, get_git_branch, get_working_dir
from agendum.models import AgentHandoffRecord, TaskStatus
from agendum.task_graph import suggest_next_task
from agendum.tools.orchestrator._helpers import resolve_and_unblock

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from agendum.models import Agent


def register(mcp: FastMCP, stores: Any, agents: dict[str, Agent]) -> None:
    """Register task lifecycle tools on the MCP server."""

    @mcp.tool()
    def pm_task_claim(project: str, task_id: str, agent_id: str) -> str:
        """Claim a pending task and start working on it.

        Sets the assigned agent and transitions status to in_progress.
        Fails if dependencies are not yet completed.
        """
        try:
            task = stores.task.get_task(project, task_id)
        except ValueError as e:
            return f"Error: {e}"
        if not task:
            return f"Error: task '{task_id}' not found."
        if task.status not in (TaskStatus.PENDING, TaskStatus.BLOCKED):
            return f"Error: task '{task_id}' is {task.status.value}, cannot claim."

        done_ids = {t.id for t in stores.task.all_tasks(project) if t.status == TaskStatus.DONE}
        unmet = [d for d in task.depends_on if d not in done_ids]
        if unmet:
            return f"Error: cannot claim '{task_id}': unmet dependencies: {', '.join(unmet)}"

        stores.task.update_task(project, task_id, assigned=agent_id, status=TaskStatus.IN_PROGRESS)
        stores.task.add_progress(project, task_id, agent_id, "Claimed task")

        if agent_id in agents:
            agents[agent_id].last_task = task_id

        return f"Claimed {task_id} for agent '{agent_id}'. Status: in_progress."

    @mcp.tool()
    def pm_task_progress(project: str, task_id: str, message: str, agent_id: str = "unknown") -> str:
        """Log a progress update on a task. Use this to record what you've done so far.

        Progress entries are appended to the task's log and visible to other agents.
        This does NOT change the task's status — use pm_task_complete or pm_task_block for that.
        """
        try:
            task = stores.task.add_progress(project, task_id, agent_id, message)
        except ValueError as e:
            return f"Error: {e}"
        if not task:
            return f"Error: task '{task_id}' not found."
        return f"Logged progress on {task_id}: {message}"

    @mcp.tool()
    def pm_task_complete(project: str, task_id: str, agent_id: str = "unknown") -> str:
        """Mark a task as done. Auto-unblocks tasks that depend on this one.

        If acceptance criteria are defined, ensure they are met before completing.
        Dependent tasks will automatically transition from blocked to pending.
        """
        try:
            task = stores.task.get_task(project, task_id)
        except ValueError as e:
            return f"Error: {e}"
        if not task:
            return f"Error: task '{task_id}' not found."

        warning = ""
        if task.acceptance_criteria:
            warning = f" Note: {len(task.acceptance_criteria)} acceptance criteria defined — ensure they are met."

        stores.task.update_task(project, task_id, status=TaskStatus.DONE)
        stores.task.add_progress(project, task_id, agent_id, "Completed task")

        unblocked = resolve_and_unblock(stores, project, task_id)

        # Auto-archive completed task
        try:
            stores.task.archive_task(project, task_id)
            auto_archived = True
        except (FileNotFoundError, ValueError):
            auto_archived = False

        result = f"Completed {task_id}.{warning}"
        if unblocked:
            result += f" Unblocked: {', '.join(unblocked)}"
        if auto_archived:
            result += " (archived)"
        return result

    @mcp.tool()
    def pm_task_block(project: str, task_id: str, reason: str, agent_id: str = "unknown") -> str:
        """Mark a task as blocked with a reason. Use when you cannot proceed."""
        try:
            task = stores.task.get_task(project, task_id)
        except ValueError as e:
            return f"Error: {e}"
        if not task:
            return f"Error: task '{task_id}' not found."
        stores.task.update_task(project, task_id, status=TaskStatus.BLOCKED)
        stores.task.add_progress(project, task_id, agent_id, f"Blocked: {reason}")
        return f"Blocked {task_id}: {reason}"

    @mcp.tool()
    def pm_task_handoff(
        project: str,
        task_id: str,
        agent_id: str = "unknown",
        completed: list[str] | None = None,
        remaining: list[str] | None = None,
        key_files: list[str] | None = None,
        decisions: list[str] | None = None,
        gotchas: list[str] | None = None,
        next_agent_hints: dict | None = None,
        device: str | None = None,
        git_branch: str | None = None,
        working_dir: str | None = None,
        handoff_context: str = "",
    ) -> str:
        """Write structured handoff context for the next agent picking up this task.

        Use completed/remaining lists to describe what's done and what's next.
        key_files, decisions, and gotchas help the next agent orient immediately.
        next_agent_hints is optional JSON: {"category": "code-complex", "model": "claude-opus"}.
        device/git_branch/working_dir are auto-detected if not provided.

        Legacy: passing handoff_context as a plain string still works (stored as free text).
        """
        try:
            task = stores.task.get_task(project, task_id)
        except ValueError as e:
            return f"Error: {e}"
        if not task:
            return f"Error: task '{task_id}' not found."

        # If using the new structured format
        if completed is not None or remaining is not None:
            hints: dict = next_agent_hints or {}

            record = AgentHandoffRecord(
                agent_id=agent_id,
                agent_type=None,
                device=device or get_device_name(),
                git_branch=git_branch or get_git_branch(),
                working_dir=working_dir or get_working_dir(),
                completed=completed or [],
                remaining=remaining or [],
                key_files=key_files or [],
                decisions=decisions or [],
                gotchas=gotchas or [],
                next_agent_hints=hints,
            )

            updated_history = task.agent_history + [record]
            stores.task.update_task(
                project,
                task_id,
                structured_handoff=record,
                agent_history=updated_history,
            )
            stores.task.add_progress(project, task_id, agent_id, "Wrote structured handoff context")
            done_count = len(record.completed)
            todo_count = len(record.remaining)
            return f"Handoff context saved for {task_id}. Done: {done_count} items, remaining: {todo_count} items."

        # Legacy free-text fallback
        text = handoff_context
        stores.task.update_task(project, task_id, handoff=text)
        stores.task.add_progress(project, task_id, agent_id, "Wrote handoff context")
        return f"Handoff context saved for {task_id}."

    @mcp.tool()
    def pm_task_next(project: str, agent_type: str | None = None, preferred_types: str | None = None) -> str:
        """Suggest the best next task to work on.

        Considers: unmet dependencies (skipped), priority (higher first),
        type preference match, and task complexity. Use pm_task_claim to start it.
        """
        try:
            all_tasks = stores.task.list_tasks(project)
            archived = stores.task.list_archived_tasks(project)
        except ValueError as e:
            return f"Error: {e}"
        type_list = preferred_types.split(",") if preferred_types else None
        task = suggest_next_task(all_tasks + archived, preferred_types=type_list)

        if not task:
            in_progress = [t for t in all_tasks if t.status == TaskStatus.IN_PROGRESS]
            blocked = [t for t in all_tasks if t.status == TaskStatus.BLOCKED]
            if in_progress:
                return f"No pending tasks available. {len(in_progress)} task(s) in progress."
            if blocked:
                return f"No pending tasks. {len(blocked)} task(s) blocked."
            return "No tasks available. All done or no tasks created yet."

        deps_str = f" (after: {','.join(task.depends_on)})" if task.depends_on else ""
        return (
            f"Suggested next task:\n"
            f"  {task.id}: {task.title}\n"
            f"  Priority: {task.priority.value} | Type: {task.type.value}{deps_str}\n"
            f"  Context: {task.context[:200] if task.context else 'none'}\n"
            f"\nUse pm_task_claim to start working on it."
        )
