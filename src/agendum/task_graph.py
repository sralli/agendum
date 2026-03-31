"""Dependency resolution engine for task management."""

from __future__ import annotations

from agendum.models import Task, TaskPriority, TaskStatus


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
    """Detect dependency cycles using iterative DFS. Safe for large graphs."""
    graph: dict[str, list[str]] = {}
    for task in tasks:
        graph[task.id] = list(task.depends_on)

    white, gray, black = 0, 1, 2
    color: dict[str, int] = {node: white for node in graph}
    parent: dict[str, str | None] = {node: None for node in graph}
    cycles: list[list[str]] = []
    seen_cycles: set[tuple[str, ...]] = set()

    for start in graph:
        if color[start] != white:
            continue

        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = gray

        while stack:
            node, dep_idx = stack[-1]
            deps = graph.get(node, [])

            if dep_idx < len(deps):
                stack[-1] = (node, dep_idx + 1)
                dep = deps[dep_idx]

                if dep not in color:
                    continue  # dep references a non-existent task

                if color[dep] == gray:
                    # Found a cycle — trace back
                    cycle = [dep]
                    for sn, _ in reversed(stack):
                        cycle.append(sn)
                        if sn == dep:
                            break
                    cycle.reverse()
                    # Deduplicate by normalizing cycle rotation
                    min_idx = cycle.index(min(cycle[:-1]))
                    normalized = tuple(cycle[min_idx:] + cycle[1 : min_idx + 1])
                    if normalized not in seen_cycles:
                        seen_cycles.add(normalized)
                        cycles.append(list(cycle))
                elif color[dep] == white:
                    color[dep] = gray
                    parent[dep] = node
                    stack.append((dep, 0))
            else:
                color[node] = black
                stack.pop()

    return cycles


def topological_levels(tasks: list[Task]) -> list[list[str]]:
    """Group tasks into execution levels by dependency depth.

    Level 0: tasks with no dependencies
    Level 1: tasks whose dependencies are all in level 0
    Level N: tasks whose dependencies are all in levels < N

    Returns list of levels, each level is a list of task IDs.
    Raises ValueError if cycles are detected.
    """
    task_map = {t.id: t for t in tasks}
    levels: dict[str, int] = {}

    def get_level(task_id: str, visiting: set[str] | None = None) -> int:
        if task_id in levels:
            return levels[task_id]
        if visiting is None:
            visiting = set()
        if task_id in visiting:
            raise ValueError(f"Cycle detected involving {task_id}")
        visiting.add(task_id)

        task = task_map.get(task_id)
        if not task or not task.depends_on:
            levels[task_id] = 0
            return 0

        max_dep = -1
        for dep_id in task.depends_on:
            if dep_id in task_map:
                max_dep = max(max_dep, get_level(dep_id, visiting))
        levels[task_id] = max_dep + 1
        return levels[task_id]

    for t in tasks:
        get_level(t.id)

    # Group by level
    grouped: dict[int, list[str]] = {}
    for task_id, level in levels.items():
        grouped.setdefault(level, []).append(task_id)

    return [sorted(grouped[i]) for i in sorted(grouped)]


_PRIORITY_ORDER = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
}


def suggest_next_task(
    tasks: list[Task],
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
        task_type_str = task.type.value
        if preferred_types and task_type_str in preferred_types:
            type_match = -1  # Negative = better (for sorting)

        dep_count = len(task.depends_on)

        return (priority_score, type_match, dep_count)

    candidates.sort(key=score)
    return candidates[0]
