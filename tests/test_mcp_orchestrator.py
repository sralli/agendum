"""Integration tests for orchestrator MCP tools."""

from __future__ import annotations

import json

import pytest

from agendum.models import TaskStatus
from tests.conftest import call


@pytest.fixture
async def setup(mcp_server):
    """Create a project to work with."""
    mcp, stores, agents = mcp_server
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="myapp", description="Test app")
    return mcp, stores, agents


def _tasks_json(tasks: list[dict]) -> str:
    return json.dumps(tasks)


async def _create_and_approve(mcp, project, goal, tasks, **kwargs):
    """Helper: create a plan and approve it for execution."""
    result = await call(
        mcp,
        "pm_orchestrate_plan",
        project=project,
        goal=goal,
        tasks_json=_tasks_json(tasks),
        **kwargs,
    )
    # Extract plan ID from result (always plan-NNN)
    plan_id = "plan-001"
    for line in result.splitlines():
        if "Plan Created:" in line:
            plan_id = line.split("Plan Created:")[1].strip()
            break
    await call(mcp, "pm_orchestrate_approve", project=project, plan_id=plan_id)
    return result, plan_id


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
        # A and B should be at level 0, C at level 1
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
        # Level 1 (index 1) should be a checkpoint (every 2)
        assert plan.levels[1].is_checkpoint is True

    async def test_all_plans_start_as_draft(self, setup):
        """Plans always start as DRAFT regardless of policy."""
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


class TestOrchestrateNext:
    async def test_next_returns_level0(self, setup):
        mcp, _, _ = setup
        await _create_and_approve(mcp, "myapp", "Test", PARALLEL_TASKS)
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-001")
        assert "Level 0" in result
        assert "Task A" in result
        assert "Task B" in result

    async def test_draft_plan_blocked(self, setup):
        """Unapproved plans cannot dispatch tasks."""
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

        # Task should be marked done
        task = stores.task.get_task("myapp", tasks[0].id)
        assert task.status.value == "done"

        # Trace should be written
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

        # Block the second task first so resolve_completions can unblock it
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


class TestFullFlow:
    """End-to-end: plan -> next -> report -> next -> complete."""

    async def test_two_level_flow(self, setup):
        mcp, stores, _ = setup

        # Create plan with 2 levels and approve
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

        # Block the dependent so it can be unblocked
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
        # Plan is now EXECUTING — cannot approve again
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
        # Pass spec review
        await call(
            mcp,
            "pm_orchestrate_review",
            project="myapp",
            task_id=task_id,
            stage="spec",
            passed=True,
        )
        # Pass quality review
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

        # Block second so it can be unblocked
        stores.task.update_task("myapp", second.id, status=TaskStatus.BLOCKED)

        # Report first done (goes to review)
        await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=first.id,
            status="done",
        )

        # Pass both reviews
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
        """When review_required=False, report(done) goes straight to DONE."""
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

        # Verify persistence
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
