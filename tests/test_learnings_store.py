"""Tests for LearningsStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from agendum.store.learnings_store import LearningsStore


@pytest.fixture
def store(tmp_root: Path) -> LearningsStore:
    return LearningsStore(tmp_root)


def test_add_learning(store: LearningsStore):
    lid = store.add_learning("Always run tests before committing.", tags=["workflow"], source_project="myproj")
    assert lid == "learning-001"

    learnings = store.list_learnings()
    assert len(learnings) == 1
    assert learnings[0]["id"] == "learning-001"
    assert learnings[0]["content"] == "Always run tests before committing."
    assert learnings[0]["tags"] == ["workflow"]
    assert learnings[0]["source_project"] == "myproj"


def test_list_learnings(store: LearningsStore):
    store.add_learning("Learning A", tags=["a"])
    store.add_learning("Learning B", tags=["b"])
    store.add_learning("Learning C", tags=["a", "c"])

    all_learnings = store.list_learnings()
    assert len(all_learnings) == 3


def test_list_by_tag(store: LearningsStore):
    store.add_learning("Learning A", tags=["a"])
    store.add_learning("Learning B", tags=["b"])
    store.add_learning("Learning C", tags=["a", "c"])

    filtered = store.list_learnings(tag="a")
    assert len(filtered) == 2
    ids = {l["id"] for l in filtered}
    assert "learning-001" in ids
    assert "learning-003" in ids


def test_search_learnings(store: LearningsStore):
    store.add_learning("Use atomic writes for safety.", tags=["io"])
    store.add_learning("Pydantic v2 uses model_validate.", tags=["pydantic"])
    store.add_learning("Atomic operations prevent corruption.", tags=["io"])

    results = store.search_learnings("atomic")
    assert len(results) == 2

    results = store.search_learnings("pydantic")
    assert len(results) == 1  # matches content and tag of same learning
