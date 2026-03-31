"""Concrete context sources for the enrichment pipeline."""

from __future__ import annotations

from pathlib import Path

from agendum.models import BoardItem, TaskStatus, WorkPackage
from agendum.store.memory_store import MemoryStore


class ProjectRulesSource:
    """Reads CLAUDE.md or AGENTS.md from the project's git root."""

    name = "project_rules"

    def __init__(self, agendum_root: Path, max_chars: int = 3000):
        self._root = agendum_root
        self._max_chars = max_chars

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        git_root = _find_git_root(self._root)
        if not git_root:
            return package

        content = ""
        source_path = ""
        for filename in ("CLAUDE.md", "AGENTS.md"):
            path = git_root / filename
            if path.exists():
                with path.open(errors="replace") as f:
                    content = f.read(self._max_chars)
                source_path = str(path)
                break

        if not content:
            return package

        pointers = list(package.pointers)
        if source_path:
            pointers.append(f"Full file: {source_path}")

        return package.model_copy(
            update={
                "project_rules": content[: self._max_chars],
                "pointers": pointers,
            }
        )


class MemorySource:
    """Searches memory store for relevant decisions and patterns."""

    name = "memory"

    def __init__(self, memory_store: MemoryStore):
        self._store = memory_store

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        query = package.scope or item.title
        if not query:
            return package

        results = self._store.search(query)
        if not results:
            return package

        lines = []
        pointers = list(package.pointers)
        for scope, matches in results.items():
            for match in matches[:5]:  # cap per scope
                lines.append(f"- [{scope}] {match}")
            pointers.append(f'pm_memory_read(scope="{scope}")')

        return package.model_copy(
            update={
                "memory_context": "\n".join(lines),
                "pointers": pointers,
            }
        )


class DependencySource:
    """Loads decisions and notes from completed dependency items."""

    name = "dependencies"

    def __init__(self, board_store: object):
        """Accept any object with a get_item(project, item_id) method."""
        self._store = board_store

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        if not item.depends_on:
            return package

        lines = []
        pointers = list(package.pointers)
        for dep_id in item.depends_on:
            dep = self._store.get_item(project, dep_id)  # type: ignore[union-attr]
            if not dep or dep.status != TaskStatus.DONE:
                continue

            parts = [f"{dep_id} completed:"]
            if dep.decisions:
                parts.append(f"  decisions: {', '.join(dep.decisions[:5])}")
            if dep.notes:
                parts.append(f"  notes: {dep.notes[:200]}")
            lines.append("\n".join(parts))

            pointers.append(f'pm_task_get(project="{project}", task_id="{dep_id}")')

        if not lines:
            return package

        return package.model_copy(
            update={
                "dependency_context": "\n".join(lines),
                "pointers": pointers,
            }
        )


def _find_git_root(start: Path, max_depth: int = 10) -> Path | None:
    """Walk up from start to find the nearest .git/ directory.

    Stops after max_depth levels to avoid traversing to filesystem root.
    """
    for i, parent in enumerate([start, *list(start.parents)]):
        if i >= max_depth:
            break
        if (parent / ".git").exists():
            return parent
    return None
