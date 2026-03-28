"""Tests for dependency resolution engine."""

from agentpm.deps import (
    detect_cycles,
    find_unblocked_tasks,
    resolve_completions,
    suggest_next_task,
)
from agentpm.models import Task, TaskStatus


def _task(id: str, status: str = "pending", depends_on: list[str] | None = None, priority: str = "medium") -> Task:
    return Task(
        id=id,
        project="test",
        title=f"Task {id}",
        status=TaskStatus(status),
        priority=priority,
        depends_on=depends_on or [],
    )


class TestFindUnblocked:
    def test_no_deps(self):
        tasks = [_task("t1"), _task("t2")]
        unblocked = find_unblocked_tasks(tasks)
        assert len(unblocked) == 2

    def test_with_deps(self):
        tasks = [
            _task("t1", status="done"),
            _task("t2", depends_on=["t1"]),
            _task("t3", depends_on=["t2"]),
        ]
        unblocked = find_unblocked_tasks(tasks)
        assert len(unblocked) == 1
        assert unblocked[0].id == "t2"

    def test_unmet_deps(self):
        tasks = [
            _task("t1"),  # pending, not done
            _task("t2", depends_on=["t1"]),
        ]
        unblocked = find_unblocked_tasks(tasks)
        # t1 is unblocked (no deps), t2 is blocked
        assert len(unblocked) == 1
        assert unblocked[0].id == "t1"

    def test_only_pending_returned(self):
        tasks = [
            _task("t1", status="in_progress"),
            _task("t2", status="done"),
            _task("t3"),
        ]
        unblocked = find_unblocked_tasks(tasks)
        assert len(unblocked) == 1
        assert unblocked[0].id == "t3"


class TestResolveCompletions:
    def test_unblocks_dependents(self):
        tasks = [
            _task("t1", status="done"),
            _task("t2", status="blocked", depends_on=["t1"]),
        ]
        unblocked = resolve_completions(tasks, "t1")
        assert "t2" in unblocked

    def test_multi_dep_not_ready(self):
        tasks = [
            _task("t1", status="done"),
            _task("t2"),  # pending, not done
            _task("t3", status="blocked", depends_on=["t1", "t2"]),
        ]
        unblocked = resolve_completions(tasks, "t1")
        assert "t3" not in unblocked

    def test_multi_dep_all_done(self):
        tasks = [
            _task("t1", status="done"),
            _task("t2", status="done"),
            _task("t3", status="blocked", depends_on=["t1", "t2"]),
        ]
        # t2 just completed
        unblocked = resolve_completions(tasks, "t2")
        assert "t3" in unblocked


class TestDetectCycles:
    def test_no_cycles(self):
        tasks = [
            _task("t1"),
            _task("t2", depends_on=["t1"]),
            _task("t3", depends_on=["t2"]),
        ]
        assert detect_cycles(tasks) == []

    def test_simple_cycle(self):
        tasks = [
            _task("t1", depends_on=["t2"]),
            _task("t2", depends_on=["t1"]),
        ]
        cycles = detect_cycles(tasks)
        assert len(cycles) > 0

    def test_self_cycle(self):
        tasks = [_task("t1", depends_on=["t1"])]
        cycles = detect_cycles(tasks)
        assert len(cycles) > 0


class TestSuggestNext:
    def test_highest_priority_first(self):
        tasks = [
            _task("t1", priority="low"),
            _task("t2", priority="critical"),
            _task("t3", priority="medium"),
        ]
        result = suggest_next_task(tasks)
        assert result is not None
        assert result.id == "t2"

    def test_respects_deps(self):
        tasks = [
            _task("t1"),
            _task("t2", priority="critical", depends_on=["t1"]),
        ]
        result = suggest_next_task(tasks)
        assert result is not None
        assert result.id == "t1"  # t2 is blocked

    def test_no_available(self):
        tasks = [_task("t1", status="done")]
        assert suggest_next_task(tasks) is None

    def test_type_preference(self):
        tasks = [
            _task("t1", priority="medium"),
            _task("t2", priority="medium"),
        ]
        tasks[0].type = "dev"
        tasks[1].type = "docs"
        result = suggest_next_task(tasks, preferred_types=["docs"])
        assert result is not None
        assert result.id == "t2"
