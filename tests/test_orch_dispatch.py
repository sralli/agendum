"""Tests for orchestrator dispatch and report tools."""

from __future__ import annotations

from agendum.models import TaskStatus
from tests.conftest import _create_and_approve, _tasks_json, call

PARALLEL_TASKS = [
    {"title": "Task A", "type": "dev"},
    {"title": "Task B", "type": "docs"},
    {"title": "Task C", "type": "dev", "depends_on_indices": [0, 1]},
]


class TestOrchestrateNext:
    async def test_next_returns_level0(self, setup):
        mcp, _, _ = setup
        await _create_and_approve(mcp, "myapp", "Test", PARALLEL_TASKS)
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-001")
        assert "Level 0" in result
        assert "Task A" in result
        assert "Task B" in result

    async def test_draft_plan_blocked(self, setup):
        mcp, _, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json([{"title": "X"}]),
        )
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-001")
        assert "DRAFT" in result

    async def test_nonexistent_plan(self, setup):
        mcp, _, _ = setup
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-999")
        assert "Error" in result


class TestOrchestrateReport:
    async def test_report_done(self, setup):
        mcp, stores, _ = setup
        await _create_and_approve(mcp, "myapp", "Test", [{"title": "Only task"}])
        tasks = stores.task.list_tasks("myapp")
        result = await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=tasks[0].id,
            status="done",
            plan_id="plan-001",
        )
        assert "done" in result
        task = stores.task.get_task("myapp", tasks[0].id)
        assert task.status.value == "done"
        traces = stores.trace.list_traces("myapp")
        assert len(traces) == 1

    async def test_report_done_with_concerns(self, setup):
        mcp, stores, _ = setup
        await _create_and_approve(mcp, "myapp", "Test", [{"title": "Task"}])
        tasks = stores.task.list_tasks("myapp")
        result = await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=tasks[0].id,
            status="done_with_concerns",
            concerns="No error handling,Missing tests",
        )
        assert "done_with_concerns" in result
        traces = stores.trace.list_traces("myapp")
        assert "No error handling" in traces[0].concerns

    async def test_report_blocked(self, setup):
        mcp, stores, _ = setup
        await _create_and_approve(mcp, "myapp", "Test", [{"title": "Task"}])
        tasks = stores.task.list_tasks("myapp")
        result = await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=tasks[0].id,
            status="blocked",
            block_reason="Missing API credentials",
        )
        assert "blocked" in result
        task = stores.task.get_task("myapp", tasks[0].id)
        assert task.status.value == "blocked"

    async def test_report_unblocks_dependents(self, setup):
        mcp, stores, _ = setup
        await _create_and_approve(
            mcp,
            "myapp",
            "Test",
            [
                {"title": "First"},
                {"title": "Second", "depends_on_indices": [0]},
            ],
        )
        tasks = stores.task.list_tasks("myapp")
        first = next(t for t in tasks if t.title == "First")
        second = next(t for t in tasks if t.title == "Second")
        stores.task.update_task("myapp", second.id, status=TaskStatus.BLOCKED)
        result = await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=first.id,
            status="done",
        )
        assert "Unblocked" in result

    async def test_invalid_status(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id="task-001",
            status="invalid",
        )
        assert "Error" in result
