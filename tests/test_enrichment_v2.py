"""Tests for the v2 enrichment pipeline."""

from __future__ import annotations

from agendum.enrichment.pipeline import ContextEnricher, ContextSource
from agendum.models import BoardItem, WorkPackage


class FakeSource:
    """Sets memory_context on the work package."""

    name = "fake"

    def __init__(self, field: str = "memory_context", value: str = "fake memory data"):
        self._field = field
        self._value = value

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        return package.model_copy(update={self._field: self._value})


class FailingSource:
    """Always raises an exception."""

    name = "failing"

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        raise RuntimeError("boom")


def _make_item(**kwargs) -> BoardItem:
    defaults = {"id": "t-1", "project": "test", "title": "Test item"}
    defaults.update(kwargs)
    return BoardItem(**defaults)


def _make_package(item: BoardItem | None = None, **kwargs) -> WorkPackage:
    if item is None:
        item = _make_item()
    defaults: dict = {"item": item}
    defaults.update(kwargs)
    return WorkPackage(**defaults)


class TestFakeSourceProtocol:
    def test_fake_source_satisfies_protocol(self):
        source = FakeSource()
        assert isinstance(source, ContextSource)


class TestEnrichmentPipeline:
    def test_register_and_enrich(self):
        enricher = ContextEnricher()
        enricher.register(FakeSource())

        item = _make_item()
        package = _make_package(item)
        result = enricher.enrich(package, item, "test")

        assert result.memory_context == "fake memory data"

    def test_empty_enricher(self):
        enricher = ContextEnricher()

        item = _make_item()
        package = _make_package(item)
        result = enricher.enrich(package, item, "test")

        assert result.memory_context == ""
        assert result.project_rules == ""
        assert result.dependency_context == ""

    def test_budget_truncation(self):
        enricher = ContextEnricher()
        big_content = "line\n" * 2000  # ~10000 chars
        enricher.register(FakeSource(field="project_rules", value=big_content))

        item = _make_item()
        package = _make_package(item)
        result = enricher.enrich(package, item, "test")

        # project_rules budget is 3000, so it should be truncated
        assert len(result.project_rules) < len(big_content)
        assert result.project_rules.endswith("...(project_rules truncated)")

    def test_multiple_sources(self):
        enricher = ContextEnricher()
        enricher.register(FakeSource(field="memory_context", value="mem data"))
        enricher.register(FakeSource(field="project_rules", value="rules data"))

        item = _make_item()
        package = _make_package(item)
        result = enricher.enrich(package, item, "test")

        assert result.memory_context == "mem data"
        assert result.project_rules == "rules data"

    def test_disabled_source(self):
        enricher = ContextEnricher()
        enricher.register(FakeSource(field="memory_context", value="should not appear"))

        item = _make_item()
        package = _make_package(item)
        result = enricher.enrich(package, item, "test", disabled_sources=["fake"])

        assert result.memory_context == ""

    def test_unregister(self):
        enricher = ContextEnricher()
        enricher.register(FakeSource())
        assert "fake" in enricher.source_names

        enricher.unregister("fake")
        assert "fake" not in enricher.source_names

    def test_failing_source_skipped(self):
        enricher = ContextEnricher()
        enricher.register(FailingSource())
        enricher.register(FakeSource(field="memory_context", value="still works"))

        item = _make_item()
        package = _make_package(item)
        result = enricher.enrich(package, item, "test")

        # Failing source is skipped, subsequent source still applied
        assert result.memory_context == "still works"

    def test_source_names(self):
        enricher = ContextEnricher()
        enricher.register(FakeSource(field="memory_context", value="a"))
        enricher.register(FakeSource(field="project_rules", value="b"))

        # Both have name "fake"
        assert enricher.source_names == ["fake", "fake"]
