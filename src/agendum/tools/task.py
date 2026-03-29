"""Task management tools: CRUD, claim, complete, block, handoff, next."""

from __future__ import annotations

from agendum.env_context import get_device_name, get_git_branch, get_working_dir
from agendum.models import AgentHandoffRecord, TaskStatus
from agendum.task_graph import resolve_completions, suggest_next_task

_VALID_STATUSES = ", ".join(s.value for s in TaskStatus)


def register(mcp, stores, agents):
    """Register task tools on the MCP server."""

    @mcp.tool()
    def pm_task_create(
        project: str,
        title: str,
        description: str = "",
        priority: str = "medium",
        task_type: str = "dev",
        depends_on: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Create a new task in a project.

        Tasks are stored as Markdown files. Use depends_on to set task ordering.
        Acceptance criteria are checked when completing a task.
        Valid priorities: critical, high, medium, low.
        Valid types: dev, docs, email, planning, personal, ops, research, review.
        """
        try:
            task = stores.task.create_task(
                project=project,
                title=title,
                context=description,
                priority=priority,
                type=task_type,
                depends_on=depends_on or [],
                acceptance_criteria=acceptance_criteria or [],
                tags=tags or [],
            )
        except ValueError as e:
            return f"Error: {e}"
        status_note = ""
        if task.depends_on:
            status_note = f" (blocked by: {', '.join(task.depends_on)})"
        return f"Created task {task.id}: {task.title}{status_note}"

    @mcp.tool()
    def pm_task_list(
        project: str,
        status: str | None = None,
        assigned: str | None = None,
        tag: str | None = None,
        task_type: str | None = None,
    ) -> str:
        """List tasks in a project with optional filters.

        Valid statuses: pending, in_progress, blocked, review, done, cancelled.
        Returns a formatted table with status, ID, title, priority, and assignee.
        """
        status_enum = None
        if status:
            try:
                status_enum = TaskStatus(status)
            except ValueError:
                return f"Invalid status '{status}'. Valid values: {_VALID_STATUSES}"
        try:
            tasks = stores.task.list_tasks(project, status=status_enum, assigned=assigned, tag=tag, task_type=task_type)
        except ValueError as e:
            return f"Error: {e}"

        if not tasks:
            return f"No tasks found in '{project}' with the given filters."

        lines = [f"Tasks in '{project}' ({len(tasks)}):"]
        for t in tasks:
            assigned_str = f" [{t.assigned}]" if t.assigned else ""
            deps_str = f" (depends: {','.join(t.depends_on)})" if t.depends_on else ""
            lines.append(f"  [{t.status.value:^11}] {t.id}: {t.title} ({t.priority.value}){assigned_str}{deps_str}")
        return "\n".join(lines)

    @mcp.tool()
    def pm_task_get(project: str, task_id: str) -> str:
        """Get full details of a specific task including progress log, decisions, and handoff context."""
        try:
            task = stores.task.get_task(project, task_id)
        except ValueError as e:
            return f"Error: {e}"
        if not task:
            return f"Task '{task_id}' not found in project '{project}'."

        lines = [
            f"# {task.title}",
            f"ID: {task.id} | Status: {task.status.value} | Priority: {task.priority.value}",
            f"Type: {task.type.value} | Assigned: {task.assigned or 'unassigned'}",
        ]
        if task.depends_on:
            lines.append(f"Depends on: {', '.join(task.depends_on)}")
        if task.blocks:
            lines.append(f"Blocks: {', '.join(task.blocks)}")
        if task.acceptance_criteria:
            lines.append("\n## Acceptance Criteria")
            for ac in task.acceptance_criteria:
                lines.append(f"  - [ ] {ac}")
        if task.context:
            lines.append(f"\n## Context\n{task.context}")
        if task.progress:
            lines.append("\n## Progress")
            for p in task.progress:
                lines.append(f"  - [{p.timestamp.strftime('%m-%d %H:%M')}] {p.agent} — {p.message}")
        if task.decisions:
            lines.append("\n## Decisions")
            for d in task.decisions:
                lines.append(f"  - {d}")

        # Structured handoff takes priority over legacy free text
        if task.structured_handoff:
            h = task.structured_handoff
            ts = h.timestamp.strftime("%Y-%m-%d %H:%M") if h.timestamp else "?"
            ctx_parts = [f"{h.agent_id}"]
            if h.device:
                ctx_parts.append(h.device)
            if h.git_branch:
                ctx_parts.append(f"branch: {h.git_branch}")
            lines.append(f"\n## Handoff  (from {', '.join(ctx_parts)} at {ts})")
            if h.completed:
                lines.append("  Done:")
                for item in h.completed:
                    lines.append(f"    [x] {item}")
            if h.remaining:
                lines.append("  Remaining:")
                for item in h.remaining:
                    lines.append(f"    [ ] {item}")
            if h.key_files:
                lines.append(f"  Key files: {', '.join(h.key_files)}")
            if h.decisions:
                lines.append("  Decisions:")
                for d in h.decisions:
                    lines.append(f"    - {d}")
            if h.gotchas:
                lines.append("  Gotchas:")
                for g in h.gotchas:
                    lines.append(f"    ⚠ {g}")
            if h.next_agent_hints:
                hints = ", ".join(f"{k}: {v}" for k, v in h.next_agent_hints.items())
                lines.append(f"  Next agent hints: {hints}")
        elif task.handoff:
            lines.append(f"\n## Handoff\n{task.handoff}")

        if task.agent_history:
            lines.append(f"\n## Agent History ({len(task.agent_history)} handoff(s))")
            for rec in task.agent_history:
                ts = rec.timestamp.strftime("%Y-%m-%d %H:%M") if rec.timestamp else "?"
                lines.append(f"  - {rec.agent_id} ({rec.agent_type or 'unknown'}) at {ts}")

        return "\n".join(lines)

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
            return f"Task '{task_id}' not found."
        if task.status not in (TaskStatus.PENDING, TaskStatus.BLOCKED):
            return f"Task '{task_id}' is {task.status.value}, cannot claim."

        all_tasks = stores.task.list_tasks(project)
        done_ids = {t.id for t in all_tasks if t.status == TaskStatus.DONE}
        unmet = [d for d in task.depends_on if d not in done_ids]
        if unmet:
            return f"Cannot claim '{task_id}': unmet dependencies: {', '.join(unmet)}"

        stores.task.update_task(project, task_id, assigned=agent_id, status=TaskStatus.IN_PROGRESS)
        stores.task.add_progress(project, task_id, agent_id, "Claimed task")

        if agent_id in agents:
            agents[agent_id].current_task = task_id

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
            return f"Task '{task_id}' not found."
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
            return f"Task '{task_id}' not found."

        warning = ""
        if task.acceptance_criteria:
            warning = f" Note: {len(task.acceptance_criteria)} acceptance criteria defined — ensure they are met."

        stores.task.update_task(project, task_id, status=TaskStatus.DONE)
        stores.task.add_progress(project, task_id, agent_id, "Completed task")

        all_tasks = stores.task.list_tasks(project)
        unblocked = resolve_completions(all_tasks, task_id)
        for uid in unblocked:
            stores.task.update_task(project, uid, status=TaskStatus.PENDING)
            stores.task.add_progress(project, uid, "system", f"Auto-unblocked: dependency {task_id} completed")

        result = f"Completed {task_id}.{warning}"
        if unblocked:
            result += f" Unblocked: {', '.join(unblocked)}"
        return result

    @mcp.tool()
    def pm_task_block(project: str, task_id: str, reason: str, agent_id: str = "unknown") -> str:
        """Mark a task as blocked with a reason. Use when you cannot proceed."""
        try:
            task = stores.task.get_task(project, task_id)
        except ValueError as e:
            return f"Error: {e}"
        if not task:
            return f"Task '{task_id}' not found."
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
            return f"Task '{task_id}' not found."

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
                project, task_id,
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
        except ValueError as e:
            return f"Error: {e}"
        type_list = preferred_types.split(",") if preferred_types else None
        task = suggest_next_task(all_tasks, agent_type=agent_type, preferred_types=type_list)

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
