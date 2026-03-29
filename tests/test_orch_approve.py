"""Tests for orchestrator approve tool."""

from __future__ import annotations

from tests.conftest import _create_and_approve, _tasks_json, call


class TestOrchestrateApprove:
    async def test_approve_draft(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json([{"title": "Task"}]),
        )
        result = await call(
            mcp,
            "pm_orchestrate_approve",
            project="myapp",
            plan_id="plan-001",
            decision="approve",
        )
        assert "approved" in result.lower()
        plan = stores.plan.get_plan("myapp", "plan-001")
        assert plan.status.value == "executing"

    async def test_reject_plan(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json([{"title": "Task"}]),
        )
        result = await call(
            mcp,
            "pm_orchestrate_approve",
            project="myapp",
            plan_id="plan-001",
            decision="reject",
        )
        assert "rejected" in result.lower()
        plan = stores.plan.get_plan("myapp", "plan-001")
        assert plan.status.value == "cancelled"

    async def test_modify_plan(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json([{"title": "Task"}]),
        )
        result = await call(
            mcp,
            "pm_orchestrate_approve",
            project="myapp",
            plan_id="plan-001",
            decision="modify",
        )
        assert "DRAFT" in result
        plan = stores.plan.get_plan("myapp", "plan-001")
        assert plan.status.value == "draft"

    async def test_cannot_approve_executing(self, setup):
        mcp, _, _ = setup
        await _create_and_approve(mcp, "myapp", "Test", [{"title": "Task"}])
        result = await call(
            mcp,
            "pm_orchestrate_approve",
            project="myapp",
            plan_id="plan-001",
            decision="approve",
        )
        assert "Error" in result

    async def test_approve_with_notes(self, setup):
        mcp, _, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json([{"title": "Task"}]),
        )
        result = await call(
            mcp,
            "pm_orchestrate_approve",
            project="myapp",
            plan_id="plan-001",
            decision="approve",
            notes="Looks good to me",
        )
        assert "Looks good to me" in result
