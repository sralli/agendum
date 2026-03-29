"""Tests for memory store."""

import tempfile
from pathlib import Path

from agendum.store.memory_store import MemoryStore


def _tmp_root():
    root = Path(tempfile.mkdtemp()) / ".agentpm"
    root.mkdir(parents=True)
    return root


class TestMemoryStore:
    def test_write_and_read(self):
        store = MemoryStore(_tmp_root())
        store.write("project", "Test content")
        assert store.read("project") == "Test content"

    def test_read_empty(self):
        store = MemoryStore(_tmp_root())
        assert store.read("project") == ""

    def test_append(self):
        store = MemoryStore(_tmp_root())
        store.append("decisions", "Use PostgreSQL", "claude")
        store.append("decisions", "Use TypeScript", "cursor")
        content = store.read("decisions")
        assert "Use PostgreSQL" in content
        assert "Use TypeScript" in content
        assert "(claude)" in content

    def test_search(self):
        store = MemoryStore(_tmp_root())
        store.write("project", "We use React for frontend")
        store.write("decisions", "Chose PostgreSQL over MySQL")
        store.write("patterns", "Always use TypeScript strict mode")

        results = store.search("use")
        assert "project" in results
        assert "patterns" in results

    def test_search_no_match(self):
        store = MemoryStore(_tmp_root())
        store.write("project", "Hello world")
        results = store.search("nonexistent")
        assert results == {}

    def test_list_scopes(self):
        store = MemoryStore(_tmp_root())
        store.write("project", "x")
        store.write("decisions", "y")
        scopes = store.list_scopes()
        assert "project" in scopes
        assert "decisions" in scopes
