"""Context enrichment pipeline — Protocol-based extensible architecture."""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable

from agendum.models import BoardItem, WorkPackage


@runtime_checkable
class ContextSource(Protocol):
    """A pluggable source that can enrich a work package.

    Each source receives only the specific store it needs via its constructor.
    The enrich method must return a new WorkPackage (never mutate the input).
    """

    name: str

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage: ...


class ContextEnricher:
    """Registry of context sources. Enriches packages by folding over sources."""

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
        package: WorkPackage,
        item: BoardItem,
        project: str,
        disabled_sources: list[str] | None = None,
        max_context_chars: int = 8000,
        field_budgets: dict[str, int] | None = None,
    ) -> WorkPackage:
        """Enrich a work package with live data from all registered sources.

        Sources disabled by name are skipped. Budget truncation is applied
        after all sources have contributed.
        """
        for source in self._sources:
            if disabled_sources and source.name in disabled_sources:
                continue
            try:
                package = source.enrich(package, item, project)
            except Exception:
                print(f"agendum: enrichment source '{source.name}' failed, skipping", file=sys.stderr)

        return self._apply_budget(package, max_context_chars, field_budgets)

    def _apply_budget(
        self, package: WorkPackage, max_chars: int, field_budgets: dict[str, int] | None = None
    ) -> WorkPackage:
        """Truncate enrichment fields to stay within budget.

        Priority (highest first): project_rules, dependency_context, memory_context.
        """
        defaults = {"project_rules": 3000, "dependency_context": 2000, "memory_context": 2000}
        budgets = field_budgets or defaults
        budget = _BudgetAllocator(max_chars)

        project_rules = budget.allocate(package.project_rules, budgets.get("project_rules", 3000), "project_rules")
        dependency_context = budget.allocate(
            package.dependency_context, budgets.get("dependency_context", 2000), "dependency_context"
        )
        memory_context = budget.allocate(package.memory_context, budgets.get("memory_context", 2000), "memory_context")

        return package.model_copy(
            update={
                "project_rules": project_rules,
                "dependency_context": dependency_context,
                "memory_context": memory_context,
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
        suffix = f"\n...({field_name} truncated)"
        self._remaining = max(0, self._remaining - len(truncated) - len(suffix))
        return truncated + suffix
