"""Concurrent write safety tests — verify no data loss under multi-threaded access."""

from __future__ import annotations

from pathlib import Path
from threading import Lock, Thread

from agendum.store.board_store import BoardStore
from agendum.store.memory_store import MemoryStore
from agendum.store.project_store import ProjectStore


def test_concurrent_add_progress_no_data_loss(tmp_path: Path) -> None:
    """20 threads adding progress to the same item must all survive."""
    root = tmp_path / ".agendum"
    root.mkdir()
    project_store = ProjectStore(root)
    project_store.init_board()
    project_store.create_project("demo")
    store = BoardStore(root)
    item = store.create_item("demo", "Concurrent test item")

    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            store.add_progress("demo", item.id, f"agent-{i}", f"Step {i}")
        except Exception as e:
            errors.append(e)

    threads = [Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected errors: {errors}"
    result = store.get_item("demo", item.id)
    assert result is not None
    assert len(result.progress) == 20, f"Expected 20 entries, got {len(result.progress)}"


def test_concurrent_create_item_unique_ids(tmp_path: Path) -> None:
    """10 threads creating items simultaneously must produce unique IDs."""
    root = tmp_path / ".agendum"
    root.mkdir()
    project_store = ProjectStore(root)
    project_store.init_board()
    project_store.create_project("demo")
    store = BoardStore(root)

    ids: list[str] = []
    lock = Lock()
    errors: list[Exception] = []

    def worker() -> None:
        try:
            created = store.create_item("demo", "Parallel item")
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
    root = tmp_path / ".agendum"
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
