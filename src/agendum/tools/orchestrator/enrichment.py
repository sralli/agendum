"""Context enrichment pipeline — Protocol-based extensible architecture."""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable

from agendum.models import ContextPacket, Task


@runtime_checkable
class ContextSource(Protocol):
    """A pluggable source that can enrich a context packet.

    Each source receives only the specific store it needs via its constructor.
    The enrich method must return a new ContextPacket (never mutate the input).
    """

    name: str

    def enrich(self, packet: ContextPacket, task: Task, project: str) -> ContextPacket: ...


class ContextEnricher:
    """Registry of context sources. Enriches packets by folding over sources."""

    def __init__(self) -> None:
        self._sources: list[ContextSource] = []

    def register(self, source: ContextSource) -> None:
        """Add a context source to the pipeline."""
        self._sources.append(source)

    def unregister(self, name: str) -> None:
        """Remove a context source by name."""
        self._sources = [s for s in self._sources if s.name != name]

    @property
    def source_names(self) -> list[str]:
        """List registered source names."""
        return [s.name for s in self._sources]

    def enrich(
        self,
        packet: ContextPacket,
        task: Task,
        project: str,
        disabled_sources: list[str] | None = None,
        max_context_chars: int = 8000,
    ) -> ContextPacket:
        """Enrich a static context packet with live data from all registered sources.

        Sources disabled by policy are skipped. Budget truncation is applied
        after all sources have contributed.
        """
        for source in self._sources:
            if disabled_sources and source.name in disabled_sources:
                continue
            try:
                packet = source.enrich(packet, task, project)
            except Exception:
                print(f"agendum: enrichment source '{source.name}' failed, skipping", file=sys.stderr)

        return self._apply_budget(packet, max_context_chars)

    def _apply_budget(self, packet: ContextPacket, max_chars: int) -> ContextPacket:
        """Truncate enrichment fields to stay within budget.

        Priority (highest first): project_rules, dependency_outputs,
        memory_context, review_history.
        """
        budget = _BudgetAllocator(max_chars)

        project_rules = budget.allocate(packet.project_rules, 3000, "project_rules")
        dependency_outputs = budget.allocate(packet.dependency_outputs, 2000, "dependency_outputs")
        memory_context = budget.allocate(packet.memory_context, 2000, "memory_context")
        review_history = budget.allocate(packet.review_history, 1000, "review_history")

        return packet.model_copy(
            update={
                "project_rules": project_rules,
                "dependency_outputs": dependency_outputs,
                "memory_context": memory_context,
                "review_history": review_history,
            }
        )


class _BudgetAllocator:
    """Tracks remaining budget and truncates content with pointer suffixes."""

    def __init__(self, total: int) -> None:
        self._remaining = total

    def allocate(self, content: str, max_chars: int, field_name: str) -> str:
        """Allocate budget for a field. Truncates if over budget."""
        if not content:
            return ""

        limit = min(max_chars, self._remaining)
        if limit <= 0:
            return ""

        if len(content) <= limit:
            self._remaining -= len(content)
            return content

        truncated = content[:limit].rsplit("\n", 1)[0]  # truncate at last newline
        suffix = f"\n... ({field_name} truncated)"
        self._remaining -= len(truncated) + len(suffix)
        return truncated + suffix
