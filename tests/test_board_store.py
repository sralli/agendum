"""Tests for BoardStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from agendum.models import TaskStatus
from agendum.store.board_store import BoardStore


@pytest.fixture
def store(tmp_root: Path) -> BoardStore:
    return BoardStore(tmp_root)


def test_create_item(store: BoardStore):
    item = store.create_item("proj", "First item")
    assert item.id == "item-001"
    assert item.title == "First item"
    assert item.project == "proj"
    assert item.status == TaskStatus.PENDING


def test_sequential_ids(store: BoardStore):
    i1 = store.create_item("proj", "Item 1")
    i2 = store.create_item("proj", "Item 2")
    i3 = store.create_item("proj", "Item 3")
    assert i1.id == "item-001"
    assert i2.id == "item-002"
    assert i3.id == "item-003"


def test_get_item(store: BoardStore):
    created = store.create_item("proj", "Get me")
    fetched = store.get_item("proj", created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "Get me"


def test_get_nonexistent(store: BoardStore):
    store.ensure_project("proj")
    assert store.get_item("proj", "item-999") is None


def test_list_items(store: BoardStore):
    store.create_item("proj", "A")
    store.create_item("proj", "B")
    store.create_item("proj", "C")
    items = store.list_items("proj")
    assert len(items) == 3


def test_list_with_status_filter(store: BoardStore):
    store.create_item("proj", "Pending one")
    store.create_item("proj", "Done one", status=TaskStatus.DONE)
    store.create_item("proj", "Pending two")

    pending = store.list_items("proj", status=TaskStatus.PENDING)
    assert len(pending) == 2
    done = store.list_items("proj", status=TaskStatus.DONE)
    assert len(done) == 1


def test_update_item(store: BoardStore):
    item = store.create_item("proj", "Update me")
    updated = store.update_item("proj", item.id, status=TaskStatus.IN_PROGRESS, tags=["urgent"])
    assert updated is not None
    assert updated.status == TaskStatus.IN_PROGRESS
    assert updated.tags == ["urgent"]

    # Verify persistence
    fetched = store.get_item("proj", item.id)
    assert fetched is not None
    assert fetched.status == TaskStatus.IN_PROGRESS


def test_add_progress(store: BoardStore):
    item = store.create_item("proj", "Progress me")
    updated = store.add_progress("proj", item.id, "agent-1", "Did something")
    assert updated is not None
    assert len(updated.progress) == 1
    assert updated.progress[0].agent == "agent-1"
    assert updated.progress[0].message == "Did something"


def test_done_items_accessible(store: BoardStore):
    """Done items stay in board/ and are still accessible."""
    item = store.create_item("proj", "Will be done")
    store.update_item("proj", item.id, status=TaskStatus.DONE)

    # Should still be gettable
    fetched = store.get_item("proj", item.id)
    assert fetched is not None
    assert fetched.status == TaskStatus.DONE

    # Should appear in list_items
    all_items = store.list_items("proj")
    assert any(i.id == item.id for i in all_items)
