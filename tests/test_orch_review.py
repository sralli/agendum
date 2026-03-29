"""Tests for orchestrator review tools."""

from __future__ import annotations

from agendum.models import TaskStatus
from tests.conftest import _create_and_approve, _tasks_json, call


class TestOrchestrateReview:
    async def _create_reviewed_task(self, mcp, stores):
        """Helper: create a plan with review policy, approve, report done."""
        await call(mcp, "pm_orchestrate_policy", project="myapp", review_required=True)
        await _create_and_approve(mcp, "myapp", "Review test", [{"title": "Reviewable task"}])
        tasks = stores.task.list_tasks("myapp")
        task = tasks[0]
        result = await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=task.id,
            status="done",
            plan_id="plan-001",
        )
        return task.id, result

    async def test_review_required_holds_task(self, setup):
        mcp, stores, _ = setup
        task_id, result = await self._create_reviewed_task(mcp, stores)
        assert "awaiting review" in result
        task = stores.task.get_task("myapp", task_id)
        assert task.status == TaskStatus.REVIEW

    async def test_spec_review_pass(self, setup):
        mcp, stores, _ = setup
        task_id, _ = await self._create_reviewed_task(mcp, stores)
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="spec",
            passed=True,
        )
        assert "Spec review passed" in result

    async def test_spec_review_fail(self, setup):
        mcp, stores, _ = setup
        task_id, _ = await self._create_reviewed_task(mcp, stores)
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="spec",
            passed=False,
            issues="Missing error handling,No input validation",
        )
        assert "failed" in result.lower()
        task = stores.task.get_task("myapp", task_id)
        assert task.status == TaskStatus.IN_PROGRESS

    async def test_quality_review_pass_marks_done(self, setup):
        mcp, stores, _ = setup
        task_id, _ = await self._create_reviewed_task(mcp, stores)
        await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="spec",
            passed=True,
        )
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="quality",
            passed=True,
        )
        assert "DONE" in result
        task = stores.task.get_task("myapp", task_id)
        assert task.status == TaskStatus.DONE

    async def test_quality_review_fail(self, setup):
        mcp, stores, _ = setup
        task_id, _ = await self._create_reviewed_task(mcp, stores)
        await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="spec",
            passed=True,
        )
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="quality",
            passed=False,
            issues="Magic numbers,No docstring",
        )
        assert "failed" in result.lower()
        task = stores.task.get_task("myapp", task_id)
        assert task.status == TaskStatus.IN_PROGRESS

    async def test_review_unblocks_dependents(self, setup):
        mcp, stores, _ = setup
        await call(mcp, "pm_orchestrate_policy", project="myapp", review_required=True)
        await _create_and_approve(
            mcp,
            "myapp",
            "Unblock test",
            [
                {"title": "First"},
                {"title": "Second", "depends_on_indices": [0]},
            ],
        )
        tasks = stores.task.list_tasks("myapp")
        first = next(t for t in tasks if t.title == "First")
        second = next(t for t in tasks if t.title == "Second")
        stores.task.update_task("myapp", second.id, status=TaskStatus.BLOCKED)

        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=first.id,
            status="done",
        )
        await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=first.id,
            stage="spec",
            passed=True,
        )
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=first.id,
            stage="quality",
            passed=True,
        )
        assert "Unblocked" in result

    async def test_cannot_review_pending_task(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json([{"title": "Task"}]),
        )
        tasks = stores.task.list_tasks("myapp")
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=tasks[0].id,
            stage="spec",
            passed=True,
        )
        assert "Error" in result

    async def test_no_review_when_policy_off(self, setup):
        mcp, stores, _ = setup
        await call(mcp, "pm_orchestrate_policy", project="myapp", review_required=False)
        await _create_and_approve(mcp, "myapp", "No review", [{"title": "Direct done"}])
        tasks = stores.task.list_tasks("myapp")
        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=tasks[0].id,
            status="done",
        )
        task = stores.task.get_task("myapp", tasks[0].id)
        assert task.status == TaskStatus.DONE
