"""Tests for orchestrator planning and status tools."""

from __future__ import annotations

from tests.conftest import _create_and_approve, _tasks_json, call

SIMPLE_TASKS = [
    {
        "title": "Set up database schema",
        "type": "dev",
        "priority": "high",
        "acceptance_criteria": ["Tables created", "Migrations run"],
    },
    {"title": "Implement user model", "type": "dev", "depends_on_indices": [0], "key_files": ["src/models/user.py"]},
    {
        "title": "Add auth endpoints",
        "type": "dev",
        "depends_on_indices": [1],
        "acceptance_criteria": ["Login works", "Signup works"],
    },
]

PARALLEL_TASKS = [
    {"title": "Task A", "type": "dev"},
    {"title": "Task B", "type": "docs"},
    {"title": "Task C", "type": "dev", "depends_on_indices": [0, 1]},
]


class TestOrchestrateCreate:
    async def test_create_plan(self, setup):
        mcp, stores, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Add user authentication",
            tasks_json=_tasks_json(SIMPLE_TASKS),
        )
        assert "Plan Created: plan-001" in result
        assert "Level 0" in result
        assert "Level 1" in result
        assert "Level 2" in result
        assert "Tasks: 3" in result

    async def test_creates_tasks(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json(SIMPLE_TASKS),
        )
        tasks = stores.task.list_tasks("myapp")
        assert len(tasks) == 3

    async def test_dependencies_resolved(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test deps",
            tasks_json=_tasks_json(SIMPLE_TASKS),
        )
        tasks = stores.task.list_tasks("myapp")
        task_map = {t.title: t for t in tasks}
        impl = task_map["Implement user model"]
        assert len(impl.depends_on) == 1
        assert impl.depends_on[0] == task_map["Set up database schema"].id

    async def test_parallel_tasks_same_level(self, setup):
        mcp, stores, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test parallel",
            tasks_json=_tasks_json(PARALLEL_TASKS),
        )
        assert "Level 0" in result
        assert "Levels: 2" in result

    async def test_invalid_json(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json="not json",
        )
        assert "Error" in result

    async def test_empty_tasks(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json="[]",
        )
        assert "Error" in result

    async def test_human_required_policy(self, setup):
        mcp, stores, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json([{"title": "One task"}]),
            approval_policy="human_required",
        )
        assert "Status: draft" in result

    async def test_checkpoint_every(self, setup):
        mcp, stores, _ = setup
        tasks = [
            {"title": "A"},
            {"title": "B", "depends_on_indices": [0]},
            {"title": "C", "depends_on_indices": [1]},
        ]
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Checkpoints",
            tasks_json=_tasks_json(tasks),
            checkpoint_every=2,
        )
        plan = stores.plan.get_plan("myapp", "plan-001")
        assert plan.levels[1].is_checkpoint is True

    async def test_all_plans_start_as_draft(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp,
            "pm_orchestrate_plan",
            project="myapp",
            goal="Test",
            tasks_json=_tasks_json([{"title": "Task"}]),
            approval_policy="auto",
        )
        plan = stores.plan.get_plan("myapp", "plan-001")
        assert plan.status.value == "draft"


class TestOrchestrateStatus:
    async def test_status_shows_progress(self, setup):
        mcp, stores, _ = setup
        await _create_and_approve(mcp, "myapp", "Build auth", SIMPLE_TASKS)
        result = await call(mcp, "pm_orchestrate_status", project="myapp", plan_id="plan-001")
        assert "Build auth" in result
        assert "Level 0" in result
        assert "0/3 tasks done" in result

    async def test_status_after_completion(self, setup):
        mcp, stores, _ = setup
        await _create_and_approve(mcp, "myapp", "Simple", [{"title": "One task"}])
        tasks = stores.task.list_tasks("myapp")
        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=tasks[0].id,
            status="done",
            plan_id="plan-001",
        )
        result = await call(mcp, "pm_orchestrate_status", project="myapp", plan_id="plan-001")
        assert "1/1 tasks done" in result

    async def test_nonexistent_plan(self, setup):
        mcp, _, _ = setup
        result = await call(mcp, "pm_orchestrate_status", project="myapp", plan_id="plan-999")
        assert "Error" in result
