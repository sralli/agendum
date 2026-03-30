"""Task management tools: CRUD (create, list, get)."""

from __future__ import annotations

from agendum.models import TaskStatus

_VALID_STATUSES = ", ".join(s.value for s in TaskStatus)


def register(mcp, stores, agents):
    """Register task CRUD tools on the MCP server."""

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
        review_checklist: list[str] | None = None,
        test_requirements: list[str] | None = None,
        key_files: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> str:
        """Create a new task in a project.

        Tasks are stored as Markdown files. Use depends_on to set task ordering.
        Acceptance criteria are checked when completing a task.
        Valid priorities: critical, high, medium, low.
        Valid types: dev, docs, email, planning, personal, ops, research, review.

        Optional metadata lists:
        - review_checklist: items to verify during code review.
        - test_requirements: tests that must pass before completion.
        - key_files: files relevant to this task.
        - constraints: rules or limits the implementer must follow.
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
                review_checklist=review_checklist or [],
                test_requirements=test_requirements or [],
                key_files=key_files or [],
                constraints=constraints or [],
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
        include_archived: bool = False,
    ) -> str:
        """List tasks in a project with optional filters.

        Valid statuses: pending, in_progress, blocked, review, done, cancelled.
        Returns a formatted table with status, ID, title, priority, and assignee.
        Set include_archived=True to also show archived (done/cancelled) tasks.
        """
        status_enum = None
        if status:
            try:
                status_enum = TaskStatus(status)
            except ValueError:
                return f"Invalid status '{status}'. Valid values: {_VALID_STATUSES}"
        try:
            tasks = stores.task.list_tasks(project, status=status_enum, assigned=assigned, tag=tag, task_type=task_type)
            if include_archived:
                tasks += stores.task.list_archived_tasks(
                    project, status=status_enum, assigned=assigned, tag=tag, task_type=task_type
                )
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
    def pm_task_archive(project: str, task_id: str) -> str:
        """Archive a done or cancelled task, moving it out of active listings.

        Archived tasks are still accessible via pm_task_get and pm_task_list with include_archived=True.
        """
        try:
            task = stores.task.archive_task(project, task_id)
        except (FileNotFoundError, ValueError) as e:
            return f"Error: {e}"
        return f"Archived {task_id}: {task.title}"

    @mcp.tool()
    def pm_task_archive_all(project: str) -> str:
        """Archive all done and cancelled tasks in a project.

        Bulk cleanup — moves all completed/cancelled tasks out of active listings.
        """
        tasks = stores.task.list_tasks(project)
        archivable = [t for t in tasks if t.status in (TaskStatus.DONE, TaskStatus.CANCELLED)]
        if not archivable:
            return f"No done/cancelled tasks to archive in '{project}'."
        archived = []
        errors = []
        for t in archivable:
            try:
                stores.task.archive_task(project, t.id)
                archived.append(t.id)
            except (FileNotFoundError, ValueError) as e:
                errors.append(f"{t.id}: {e}")
        result = f"Archived {len(archived)} task(s) in '{project}': {', '.join(archived)}"
        if errors:
            result += f"\nErrors: {'; '.join(errors)}"
        return result

    @mcp.tool()
    def pm_task_unarchive(project: str, task_id: str) -> str:
        """Restore an archived task back to the active task list."""
        try:
            task = stores.task.unarchive_task(project, task_id)
        except FileNotFoundError as e:
            return f"Error: {e}"
        return f"Unarchived {task_id}: {task.title} (status: {task.status.value})"

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
        if task.review_checklist:
            lines.append("\n## Review Checklist")
            for rc in task.review_checklist:
                lines.append(f"  - [ ] {rc}")
        if task.test_requirements:
            lines.append("\n## Test Requirements")
            for tr in task.test_requirements:
                lines.append(f"  - {tr}")
        if task.key_files:
            lines.append(f"\nKey files: {', '.join(task.key_files)}")
        if task.constraints:
            lines.append("\n## Constraints")
            for c in task.constraints:
                lines.append(f"  - {c}")
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
