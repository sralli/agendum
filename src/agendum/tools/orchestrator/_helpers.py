"""Shared helpers for orchestrator tools — DRY extraction."""

from __future__ import annotations

from agendum.models import TaskStatus
from agendum.task_graph import resolve_completions


def parse_csv(value: str | None) -> list[str]:
    """Split a comma-separated string into a trimmed list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def resolve_and_unblock(stores, project: str, task_id: str) -> list[str]:
    """Resolve completions for a done task and unblock dependents.

    Returns list of unblocked task IDs.
    """
    all_tasks = stores.task.all_tasks(project)
    unblocked = resolve_completions(all_tasks, task_id)
    for uid in unblocked:
        stores.task.update_task(project, uid, status=TaskStatus.PENDING)
        stores.task.add_progress(project, uid, "system", f"Auto-unblocked: dependency {task_id} completed")
    return unblocked


def check_plan_level_complete(stores, project: str, plan_id: str, task_id: str) -> list[str]:
    """Check if completing task_id finishes its plan level.

    Returns status message lines (empty if no plan or not level-completing).
    """
    if not plan_id:
        return []
    plan = stores.plan.get_plan(project, plan_id)
    if not plan:
        return []

    task_statuses = {t.id: t.status for t in stores.task.all_tasks(project)}
    for lvl in plan.levels:
        if task_id in lvl.task_ids:
            all_done = all(task_statuses.get(tid, TaskStatus.PENDING) == TaskStatus.DONE for tid in lvl.task_ids)
            if all_done:
                lines = [f"Level {lvl.level} complete!"]
                if lvl.is_checkpoint:
                    lines.append("Next level is a checkpoint — call pm_orchestrate_approve to continue.")
                return lines
            break
    return []
