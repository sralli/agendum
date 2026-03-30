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
            criteria_met=["Tests pass", "No lint errors", "No regressions in existing tests", "Changes scoped to task"],
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
            criteria_failed=["Tests pass"],
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
            criteria_met=["Tests pass", "No lint errors", "No regressions in existing tests", "Changes scoped to task"],
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
            criteria_met=["Tests pass", "No lint errors", "No regressions in existing tests", "Changes scoped to task"],
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
            criteria_met=["Tests pass", "No lint errors", "No regressions in existing tests", "Changes scoped to task"],
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

    async def _create_reviewed_task_with_ac(self, mcp, stores, acceptance_criteria=None):
        """Helper: create a plan with review policy and acceptance criteria, approve, report done."""
        await call(mcp, "pm_orchestrate_policy", project="myapp", review_required=True)
        task_def = {"title": "Task with AC"}
        if acceptance_criteria:
            task_def["acceptance_criteria"] = acceptance_criteria
        await _create_and_approve(mcp, "myapp", "AC test", [task_def])
        tasks = stores.task.list_tasks("myapp")
        task = tasks[0]
        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=task.id,
            status="done",
            plan_id="plan-001",
        )
        return task.id

    async def test_review_spec_requires_criteria_when_task_has_ac(self, setup):
        """Spec review on task with acceptance_criteria requires criteria_met/criteria_failed."""
        mcp, stores, _ = setup
        task_id = await self._create_reviewed_task_with_ac(mcp, stores, ["Login works", "Logout works"])
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="spec",
            passed=True,
        )
        assert "Error" in result
        assert "criteria_met" in result

    async def test_review_spec_criteria_failed_auto_fails(self, setup):
        """criteria_failed auto-sets passed=False."""
        mcp, stores, _ = setup
        task_id = await self._create_reviewed_task_with_ac(mcp, stores, ["A works", "B works"])
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="spec",
            passed=True,
            criteria_met=["A works"],
            criteria_failed=["B works"],
        )
        assert "failed" in result.lower()
        task = stores.task.get_task("myapp", task_id)
        assert task.status == TaskStatus.IN_PROGRESS

    async def test_review_spec_no_ac_backward_compat(self, setup):
        """Tasks without acceptance_criteria and no default checklist still work with just passed=True."""
        mcp, stores, _ = setup
        await call(mcp, "pm_orchestrate_policy", project="myapp", review_required=True)
        await _create_and_approve(mcp, "myapp", "Compat test", [{"title": "Planning task", "type": "planning"}])
        tasks = stores.task.list_tasks("myapp")
        task = tasks[0]
        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=task.id,
            status="done",
            plan_id="plan-001",
        )
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task.id,
            stage="spec",
            passed=True,
        )
        assert "Spec review passed" in result

    async def test_review_spec_default_checklist_for_dev_type(self, setup):
        """Dev tasks without explicit AC fall back to default dev checklist."""
        mcp, stores, _ = setup
        await call(mcp, "pm_orchestrate_policy", project="myapp", review_required=True)
        await _create_and_approve(mcp, "myapp", "Dev task", [{"title": "Dev work", "type": "dev"}])
        tasks = stores.task.list_tasks("myapp")
        task = tasks[0]
        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=task.id,
            status="done",
            plan_id="plan-001",
        )
        # Spec review without criteria should error because default checklist applies
        result = await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task.id,
            stage="spec",
            passed=True,
        )
        assert "Error" in result
        assert "Tests pass" in result  # from default dev checklist
