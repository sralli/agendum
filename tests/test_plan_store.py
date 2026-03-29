"""Tests for PlanStore."""

import pytest

from agendum.models import ExecutionLevel, ExecutionPlan, ExecutionStatus
from agendum.store.plan_store import PlanStore


@pytest.fixture
def plan_store(tmp_path):
    root = tmp_path / ".agendum"
    root.mkdir()
    (root / "projects" / "myapp").mkdir(parents=True)
    return PlanStore(root)


class TestPlanStore:
    def test_create_and_get(self, plan_store):
        plan = ExecutionPlan(
            id="",
            project="myapp",
            goal="Add auth",
            task_ids=["task-001", "task-002"],
            levels=[ExecutionLevel(level=0, task_ids=["task-001", "task-002"])],
        )
        created = plan_store.create_plan(plan)
        assert created.id == "plan-001"

        loaded = plan_store.get_plan("myapp", "plan-001")
        assert loaded is not None
        assert loaded.goal == "Add auth"
        assert loaded.task_ids == ["task-001", "task-002"]

    def test_auto_id_increments(self, plan_store):
        p1 = plan_store.create_plan(
            ExecutionPlan(id="", project="myapp", goal="First")
        )
        p2 = plan_store.create_plan(
            ExecutionPlan(id="", project="myapp", goal="Second")
        )
        assert p1.id == "plan-001"
        assert p2.id == "plan-002"

    def test_duplicate_id_raises(self, plan_store):
        plan_store.create_plan(
            ExecutionPlan(id="plan-001", project="myapp", goal="First")
        )
        with pytest.raises(ValueError, match="already exists"):
            plan_store.create_plan(
                ExecutionPlan(id="plan-001", project="myapp", goal="Duplicate")
            )

    def test_update_plan(self, plan_store):
        plan_store.create_plan(
            ExecutionPlan(id="", project="myapp", goal="Original")
        )
        updated = plan_store.update_plan("myapp", "plan-001", status=ExecutionStatus.EXECUTING)
        assert updated is not None
        assert updated.status == ExecutionStatus.EXECUTING

        reloaded = plan_store.get_plan("myapp", "plan-001")
        assert reloaded.status == ExecutionStatus.EXECUTING

    def test_list_plans(self, plan_store):
        plan_store.create_plan(ExecutionPlan(id="", project="myapp", goal="A"))
        plan_store.create_plan(ExecutionPlan(id="", project="myapp", goal="B"))
        plans = plan_store.list_plans("myapp")
        assert len(plans) == 2

    def test_get_nonexistent(self, plan_store):
        assert plan_store.get_plan("myapp", "plan-999") is None

    def test_list_empty(self, plan_store):
        assert plan_store.list_plans("myapp") == []

    def test_update_nonexistent(self, plan_store):
        assert plan_store.update_plan("myapp", "plan-999", goal="X") is None
