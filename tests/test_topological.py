"""Tests for topological_levels in task_graph."""

import pytest

from agendum.models import Task, TaskStatus
from agendum.task_graph import topological_levels


def _task(id: str, depends_on: list[str] | None = None) -> Task:
    return Task(
        id=id,
        project="test",
        title=f"Task {id}",
        status=TaskStatus.PENDING,
        depends_on=depends_on or [],
    )


class TestTopologicalLevels:
    def test_no_deps(self):
        tasks = [_task("t1"), _task("t2"), _task("t3")]
        levels = topological_levels(tasks)
        assert len(levels) == 1
        assert sorted(levels[0]) == ["t1", "t2", "t3"]

    def test_linear_chain(self):
        tasks = [
            _task("t1"),
            _task("t2", depends_on=["t1"]),
            _task("t3", depends_on=["t2"]),
        ]
        levels = topological_levels(tasks)
        assert len(levels) == 3
        assert levels[0] == ["t1"]
        assert levels[1] == ["t2"]
        assert levels[2] == ["t3"]

    def test_diamond(self):
        tasks = [
            _task("t1"),
            _task("t2", depends_on=["t1"]),
            _task("t3", depends_on=["t1"]),
            _task("t4", depends_on=["t2", "t3"]),
        ]
        levels = topological_levels(tasks)
        assert len(levels) == 3
        assert levels[0] == ["t1"]
        assert sorted(levels[1]) == ["t2", "t3"]
        assert levels[2] == ["t4"]

    def test_mixed_deps(self):
        tasks = [
            _task("a"),
            _task("b"),
            _task("c", depends_on=["a"]),
            _task("d", depends_on=["a", "b"]),
        ]
        levels = topological_levels(tasks)
        assert len(levels) == 2
        assert sorted(levels[0]) == ["a", "b"]
        assert sorted(levels[1]) == ["c", "d"]

    def test_cycle_raises(self):
        tasks = [
            _task("t1", depends_on=["t2"]),
            _task("t2", depends_on=["t1"]),
        ]
        with pytest.raises(ValueError, match="Cycle"):
            topological_levels(tasks)

    def test_empty(self):
        assert topological_levels([]) == []

    def test_single_task(self):
        levels = topological_levels([_task("t1")])
        assert levels == [["t1"]]

    def test_missing_dep_ignored(self):
        """Dependencies referencing non-existent tasks are ignored."""
        tasks = [_task("t1", depends_on=["nonexistent"])]
        levels = topological_levels(tasks)
        assert len(levels) == 1
        assert levels[0] == ["t1"]
