"""Tests for orchestrator full flow and policy tools."""

from __future__ import annotations

from agendum.models import TaskStatus
from tests.conftest import _create_and_approve, call


class TestFullFlow:
    """End-to-end: plan -> approve -> next -> report -> next -> complete."""

    async def test_two_level_flow(self, setup):
        mcp, stores, _ = setup

        await _create_and_approve(
            mcp,
            "myapp",
            "Two-level flow",
            [
                {"title": "Foundation"},
                {"title": "Build on top", "depends_on_indices": [0]},
            ],
        )

        # Get level 0
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-001")
        assert "Foundation" in result
        assert "Level 0" in result

        # Complete level 0 task
        tasks = stores.task.list_tasks("myapp")
        foundation = next(t for t in tasks if t.title == "Foundation")
        builder = next(t for t in tasks if t.title == "Build on top")
        stores.task.update_task("myapp", builder.id, status=TaskStatus.BLOCKED)

        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=foundation.id,
            status="done",
            plan_id="plan-001",
        )

        # Get level 1
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-001")
        assert "Build on top" in result

        # Complete level 1
        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=builder.id,
            status="done",
            plan_id="plan-001",
        )

        # Plan should be complete
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-001")
        assert "completed" in result


class TestOrchestratePolicy:
    async def test_view_default_policy(self, setup):
        mcp, _, _ = setup
        result = await call(mcp, "pm_orchestrate_policy", project="myapp")
        assert "review_required: False" in result
        assert "auto_with_review" in result

    async def test_update_policy(self, setup):
        mcp, stores, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_policy",
            project="myapp",
            review_required=False,
            max_parallel_tasks=10,
        )
        assert "review_required: False" in result
        assert "max_parallel_tasks: 10" in result

        policy = stores.project.get_policy("myapp")
        assert policy.review_required is False
        assert policy.max_parallel_tasks == 10

    async def test_update_approval_policy(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_policy",
            project="myapp",
            approval_policy="human_required",
        )
        assert "human_required" in result

    async def test_invalid_approval_policy(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_policy",
            project="myapp",
            approval_policy="invalid",
        )
        assert "Error" in result

    async def test_nonexistent_project(self, setup):
        mcp, _, _ = setup
        result = await call(mcp, "pm_orchestrate_policy", project="nonexistent")
        assert "Error" in result
