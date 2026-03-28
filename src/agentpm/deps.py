"""Dependency resolution engine for task management."""

from __future__ import annotations

from agentpm.models import Task, TaskPriority, TaskStatus


def find_unblocked_tasks(tasks: list[Task]) -> list[Task]:
    """Find tasks that are pending and have all dependencies met."""
    done_ids = {t.id for t in tasks if t.status == TaskStatus.DONE}

    unblocked = []
    for task in tasks:
        if task.status != TaskStatus.PENDING:
            continue
        if all(dep in done_ids for dep in task.depends_on):
            unblocked.append(task)
    return unblocked


def resolve_completions(tasks: list[Task], completed_id: str) -> list[str]:
    """When a task completes, find which blocked tasks should be unblocked.

    Returns list of task IDs that should transition from blocked to pending.
    """
    done_ids = {t.id for t in tasks if t.status == TaskStatus.DONE}
    done_ids.add(completed_id)

    newly_unblocked = []
    for task in tasks:
        if task.status != TaskStatus.BLOCKED:
            continue
        if completed_id not in task.depends_on:
            continue
        if all(dep in done_ids for dep in task.depends_on):
            newly_unblocked.append(task.id)

    return newly_unblocked


def detect_cycles(tasks: list[Task]) -> list[list[str]]:
    """Detect dependency cycles. Returns list of cycles found."""
    graph: dict[str, list[str]] = {}
    for task in tasks:
        graph[task.id] = task.depends_on

    visited: set[str] = set()
    in_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        if node in in_stack:
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return
        if node in visited:
            return

        visited.add(node)
        in_stack.add(node)
        path.append(node)

        for dep in graph.get(node, []):
            dfs(dep, path)

        path.pop()
        in_stack.remove(node)

    for task_id in graph:
        if task_id not in visited:
            dfs(task_id, [])

    return cycles


_PRIORITY_ORDER = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
}


def suggest_next_task(
    tasks: list[Task],
    agent_type: str | None = None,
    preferred_types: list[str] | None = None,
) -> Task | None:
    """Suggest the best next task to work on.

    Priority:
    1. Unblocked pending tasks
    2. Higher priority first
    3. Type match if agent preferences given
    4. Fewer dependencies (simpler tasks) as tiebreaker
    """
    candidates = find_unblocked_tasks(tasks)
    if not candidates:
        return None

    def score(task: Task) -> tuple[int, int, int]:
        priority_score = _PRIORITY_ORDER.get(task.priority, 2)

        type_match = 0
        task_type_str = task.type.value if hasattr(task.type, "value") else str(task.type)
        if preferred_types and task_type_str in preferred_types:
            type_match = -1  # Negative = better (for sorting)

        dep_count = len(task.depends_on)

        return (priority_score, type_match, dep_count)

    candidates.sort(key=score)
    return candidates[0]
