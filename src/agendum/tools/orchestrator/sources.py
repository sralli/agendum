"""Concrete context sources for the enrichment pipeline."""

from __future__ import annotations

from pathlib import Path

from agendum.models import ContextPacket, ProjectPolicy, Task, TaskStatus
from agendum.store.memory_store import MemoryStore
from agendum.store.project_store import ProjectStore
from agendum.store.task_store import TaskStore


class ProjectRulesSource:
    """Reads CLAUDE.md or AGENTS.md from the project's git root."""

    name = "project_rules"

    def __init__(self, agendum_root: Path, max_chars: int = 3000):
        self._root = agendum_root
        self._max_chars = max_chars

    def enrich(self, packet: ContextPacket, task: Task, project: str) -> ContextPacket:
        git_root = _find_git_root(self._root)
        if not git_root:
            return packet

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
            return packet

        pointers = list(packet.pointers)
        if source_path:
            pointers.append(f"Full file: {source_path}")

        return packet.model_copy(
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

    def enrich(self, packet: ContextPacket, task: Task, project: str) -> ContextPacket:
        # Search using goal — most likely to match relevant entries
        query = packet.goal or task.title
        if not query:
            return packet

        results = self._store.search(query)
        if not results:
            return packet

        lines = []
        pointers = list(packet.pointers)
        for scope, matches in results.items():
            for match in matches[:5]:  # cap per scope
                lines.append(f"- [{scope}] {match}")
            pointers.append(f'pm_memory_read(scope="{scope}")')

        return packet.model_copy(
            update={
                "memory_context": "\n".join(lines),
                "pointers": pointers,
            }
        )


class HandoffSource:
    """Loads handoff records from completed dependency tasks."""

    name = "handoffs"

    def __init__(self, task_store: TaskStore):
        self._store = task_store

    def enrich(self, packet: ContextPacket, task: Task, project: str) -> ContextPacket:
        if not task.depends_on:
            return packet

        lines = []
        pointers = list(packet.pointers)
        for dep_id in task.depends_on:
            dep = self._store.get_task(project, dep_id)
            if not dep or dep.status != TaskStatus.DONE:
                continue

            handoff = dep.structured_handoff
            if handoff:
                parts = [f"{dep_id} completed:"]
                if handoff.completed:
                    parts.append(f"  done: {', '.join(handoff.completed[:5])}")
                if handoff.gotchas:
                    parts.append(f"  gotchas: {', '.join(handoff.gotchas[:3])}")
                if handoff.decisions:
                    parts.append(f"  decisions: {', '.join(handoff.decisions[:3])}")
                lines.append("\n".join(parts))
            else:
                lines.append(f"{dep_id}: completed (no handoff details)")

            pointers.append(f'pm_task_get(project="{project}", task_id="{dep_id}")')

        if not lines:
            return packet

        return packet.model_copy(
            update={
                "dependency_outputs": "\n".join(lines),
                "pointers": pointers,
            }
        )


class ReviewHistorySource:
    """Extracts prior review failures from the task's progress log."""

    name = "review_history"

    def enrich(self, packet: ContextPacket, task: Task, project: str) -> ContextPacket:
        failures = []
        criteria_failed: list[str] = []

        for entry in task.progress:
            if "Review FAILED" in entry.message:
                failures.append(f"- [{entry.timestamp.strftime('%Y-%m-%d %H:%M')}] {entry.message}")
            if "Criteria failed:" in entry.message:
                # Parse "Criteria failed: X, Y" into individual criteria
                _, _, raw = entry.message.partition("Criteria failed:")
                for criterion in raw.split(","):
                    criterion = criterion.strip()
                    if criterion:
                        criteria_failed.append(criterion)

        if not failures and not criteria_failed:
            return packet

        sections: list[str] = []
        if failures:
            sections.append("Prior review failures:")
            sections.extend(failures)
        if criteria_failed:
            sections.append("Criteria that failed:")
            for c in criteria_failed:
                sections.append(f"- {c}")

        pointers = list(packet.pointers)
        pointers.append(f'pm_task_get(project="{project}", task_id="{task.id}")')

        return packet.model_copy(
            update={
                "review_history": "\n".join(sections),
                "pointers": pointers,
            }
        )


class ExternalReferencesSource:
    """Adds pointers to configured external resources (Obsidian, wikis, etc.)."""

    name = "external_references"

    def __init__(self, project_store: ProjectStore):
        self._store = project_store
        self._policy_cache: dict[str, ProjectPolicy] = {}

    def enrich(self, packet: ContextPacket, task: Task, project: str) -> ContextPacket:
        if project not in self._policy_cache:
            self._policy_cache[project] = self._store.get_policy(project)
        policy = self._policy_cache[project]
        if not policy.external_references:
            return packet

        pointers = list(packet.pointers)
        for ref in policy.external_references:
            pointers.append(f"{ref.name}: {ref.path_or_url}")

        return packet.model_copy(update={"pointers": pointers})


def _find_git_root(start: Path, max_depth: int = 10) -> Path | None:
    """Walk up from start to find the nearest .git/ directory.

    Stops after max_depth levels to avoid traversing to filesystem root.
    """
    for i, parent in enumerate([start] + list(start.parents)):
        if i >= max_depth:
            break
        if (parent / ".git").exists():
            return parent
    return None
