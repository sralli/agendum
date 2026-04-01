"""Tests for adaptive enrichment budget."""

from __future__ import annotations

from agendum.enrichment.pipeline import ContextEnricher
from agendum.models import BoardItem, WorkPackage


def _make_package(rules="x" * 5000, deps="y" * 3000, memory="z" * 3000) -> tuple[WorkPackage, BoardItem]:
    item = BoardItem(id="item-001", project="test", title="Test")
    package = WorkPackage(
        item=item,
        project_rules=rules,
        dependency_context=deps,
        memory_context=memory,
    )
    return package, item


def test_default_budget_truncates():
    """Default budget (8000) truncates as before."""
    enricher = ContextEnricher()
    package, item = _make_package()
    result = enricher.enrich(package, item, "test")
    total = len(result.project_rules) + len(result.dependency_context) + len(result.memory_context)
    assert total <= 8000


def test_small_budget_truncates_more():
    """Small budget (6000) truncates more aggressively."""
    enricher = ContextEnricher()
    package, item = _make_package()
    result = enricher.enrich(
        package,
        item,
        "test",
        max_context_chars=6000,
        field_budgets={"project_rules": 2000, "dependency_context": 1500, "memory_context": 1500},
    )
    assert len(result.project_rules) <= 2000 + 50  # +50 for truncation suffix
    assert len(result.dependency_context) <= 1500 + 50


def test_large_budget_allows_more():
    """Large budget (10000) allows more content."""
    enricher = ContextEnricher()
    package, item = _make_package(rules="x" * 3000, deps="y" * 2500, memory="z" * 2500)
    result = enricher.enrich(
        package,
        item,
        "test",
        max_context_chars=10000,
        field_budgets={"project_rules": 3000, "dependency_context": 2500, "memory_context": 2500},
    )
    # Everything fits, nothing truncated
    assert len(result.project_rules) == 3000
    assert len(result.dependency_context) == 2500
    assert len(result.memory_context) == 2500
