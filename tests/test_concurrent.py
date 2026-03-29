"""Concurrent write safety tests — verify no data loss under multi-threaded access."""

from __future__ import annotations

from pathlib import Path
from threading import Lock, Thread

import pytest

from agendum.store.memory_store import MemoryStore
from agendum.store.task_store import TaskStore


def test_concurrent_add_progress_no_data_loss(tmp_path: Path) -> None:
    """20 threads adding progress to the same task must all survive."""
    root = tmp_path / ".agentpm"
    root.mkdir()
    store = TaskStore(root)
    store.ensure_project("demo")
    task = store.create_task("demo", "Concurrent test task")

    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            store.add_progress("demo", task.id, f"agent-{i}", f"Step {i}")
        except Exception as e:
            errors.append(e)

    threads = [Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected errors: {errors}"
    result = store.get_task("demo", task.id)
    assert result is not None
    assert len(result.progress) == 20, f"Expected 20 entries, got {len(result.progress)}"


def test_concurrent_create_task_unique_ids(tmp_path: Path) -> None:
    """10 threads creating tasks simultaneously must produce unique IDs."""
    root = tmp_path / ".agentpm"
    root.mkdir()
    store = TaskStore(root)
    store.ensure_project("demo")

    ids: list[str] = []
    lock = Lock()
    errors: list[Exception] = []

    def worker() -> None:
        try:
            created = store.create_task("demo", "Parallel task")
            with lock:
                ids.append(created.id)
        except Exception as e:
            errors.append(e)

    threads = [Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected errors: {errors}"
    assert len(ids) == 10
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"


def test_concurrent_memory_append_no_data_loss(tmp_path: Path) -> None:
    """20 threads appending to the same memory scope must all survive."""
    root = tmp_path / ".agentpm"
    root.mkdir()
    (root / "memory").mkdir()
    store = MemoryStore(root)

    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            store.append("decisions", f"Decision {i}", author=f"agent-{i}")
        except Exception as e:
            errors.append(e)

    threads = [Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected errors: {errors}"
    content = store.read("decisions")
    for i in range(20):
        assert f"Decision {i}" in content, f"Missing entry for Decision {i}"
