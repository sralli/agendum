"""Tests for model routing configuration and resolution."""

from __future__ import annotations

from agendum.models import ModelRouting, ProjectPolicy, Task, TaskCategory, TaskType
from agendum.tools.orchestrator._helpers import resolve_model
from tests.conftest import _create_and_approve, call

# --- Unit tests for resolve_model ---


def _task(
    task_id: str = "task-001",
    task_type: TaskType = TaskType.DEV,
    category: TaskCategory | None = None,
) -> Task:
    return Task(id=task_id, project="test", title="Test task", type=task_type, category=category)


class TestResolveModel:
    def test_no_routing_returns_none(self):
        policy = ProjectPolicy()
        assert resolve_model(policy, _task()) is None

    def test_default_fallback(self):
        policy = ProjectPolicy(model_routing=ModelRouting(default="small"))
        assert resolve_model(policy, _task()) == "small"

    def test_by_type_beats_default(self):
        policy = ProjectPolicy(
            model_routing=ModelRouting(default="small", by_type={"dev": "large"})
        )
        assert resolve_model(policy, _task(task_type=TaskType.DEV)) == "large"
        assert resolve_model(policy, _task(task_type=TaskType.DOCS)) == "small"

    def test_by_category_beats_by_type(self):
        policy = ProjectPolicy(
            model_routing=ModelRouting(
                by_type={"dev": "small"},
                by_category={"code-complex": "large"},
            )
        )
        task = _task(task_type=TaskType.DEV, category=TaskCategory.CODE_COMPLEX)
        assert resolve_model(policy, task) == "large"

    def test_by_task_beats_everything(self):
        policy = ProjectPolicy(
            model_routing=ModelRouting(
                default="small",
                by_type={"dev": "medium"},
                by_category={"code-complex": "large"},
                by_task={"task-001": "custom"},
            )
        )
        task = _task(task_type=TaskType.DEV, category=TaskCategory.CODE_COMPLEX)
        assert resolve_model(policy, task) == "custom"

    def test_review_model(self):
        policy = ProjectPolicy(
            model_routing=ModelRouting(default="small", review="large")
        )
        assert resolve_model(policy, _task(), is_review=True) == "large"

    def test_review_model_not_used_for_non_review(self):
        policy = ProjectPolicy(
            model_routing=ModelRouting(review="large")
        )
        assert resolve_model(policy, _task(), is_review=False) is None

    def test_type_beats_review(self):
        policy = ProjectPolicy(
            model_routing=ModelRouting(
                review="large",
                by_type={"dev": "medium"},
            )
        )
        assert resolve_model(policy, _task(), is_review=True) == "medium"


# --- Integration tests: policy tool ---


class TestPolicyModelRouting:
    async def test_view_default_routing(self, setup):
        mcp, _, _ = setup
        result = await call(mcp, "pm_orchestrate_policy", project="myapp")
        assert "model_routing.default: (none)" in result
        assert "model_routing.review: (none)" in result

    async def test_set_default_model(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp, "pm_orchestrate_policy", project="myapp", model_default="small"
        )
        assert "model_routing.default: small" in result

    async def test_set_review_model(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp, "pm_orchestrate_policy", project="myapp", model_review="large"
        )
        assert "model_routing.review: large" in result

    async def test_set_by_category_via_store(self, setup):
        mcp, stores, _ = setup
        stores.project.update_policy(
            "myapp",
            model_routing=ModelRouting(by_category={"code-complex": "large", "docs": "fast"}),
        )
        result = await call(mcp, "pm_orchestrate_policy", project="myapp")
        assert "code-complex" in result
        assert "large" in result

    async def test_set_by_category_via_tool(self, setup):
        mcp, _, _ = setup
        # MCP wire protocol passes dicts (auto-parsed from JSON)
        result = await call(
            mcp,
            "pm_orchestrate_policy",
            project="myapp",
            model_by_category={"code-complex": "large"},
        )
        assert "code-complex" in result

    async def test_set_by_type_via_store(self, setup):
        mcp, stores, _ = setup
        stores.project.update_policy(
            "myapp",
            model_routing=ModelRouting(by_type={"dev": "small"}),
        )
        result = await call(mcp, "pm_orchestrate_policy", project="myapp")
        assert "dev" in result

    async def test_set_by_type_via_tool(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp,
            "pm_orchestrate_policy",
            project="myapp",
            model_by_type={"dev": "small"},
        )
        assert "dev" in result

    async def test_invalid_json_rejected(self, setup):
        mcp, _, _ = setup
        result = await call(
            mcp, "pm_orchestrate_policy", project="myapp", model_by_category="not json"
        )
        assert "Error" in result

    async def test_routing_persists(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp, "pm_orchestrate_policy", project="myapp", model_default="small", model_review="large"
        )
        policy = stores.project.get_policy("myapp")
        assert policy.model_routing.default == "small"
        assert policy.model_routing.review == "large"

    async def test_incremental_update(self, setup):
        mcp, _, _ = setup
        await call(mcp, "pm_orchestrate_policy", project="myapp", model_default="small")
        await call(mcp, "pm_orchestrate_policy", project="myapp", model_review="large")
        result = await call(mcp, "pm_orchestrate_policy", project="myapp")
        assert "model_routing.default: small" in result
        assert "model_routing.review: large" in result


# --- Integration tests: dispatch with model ---


class TestDispatchWithModel:
    async def test_next_includes_recommended_model(self, setup):
        mcp, _, _ = setup
        await call(mcp, "pm_orchestrate_policy", project="myapp", model_default="small")
        await _create_and_approve(mcp, "myapp", "Test", [{"title": "Task A", "type": "dev"}])
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-001")
        assert "**Recommended Model:** small" in result

    async def test_next_omits_model_when_not_configured(self, setup):
        mcp, _, _ = setup
        await _create_and_approve(mcp, "myapp", "Test", [{"title": "Task A", "type": "dev"}])
        result = await call(mcp, "pm_orchestrate_next", project="myapp", plan_id="plan-001")
        assert "Recommended Model" not in result

    async def test_report_includes_review_model(self, setup):
        mcp, stores, _ = setup
        await call(
            mcp,
            "pm_orchestrate_policy",
            project="myapp",
            review_required=True,
            model_review="large",
        )
        await _create_and_approve(mcp, "myapp", "Test", [{"title": "Task A"}])
        tasks = stores.task.list_tasks("myapp")
        result = await call(
            mcp,
            "pm_orchestrate_report",
            project="myapp",
            task_id=tasks[0].id,
            status="done",
            plan_id="plan-001",
        )
        assert "Review model: large" in result


# --- Integration tests: agent suggest with model ---


class TestAgentSuggestWithModel:
    async def test_suggest_includes_policy_model(self, setup):
        mcp, stores, _ = setup
        stores.project.update_policy(
            "myapp",
            model_routing=ModelRouting(by_type={"dev": "small"}),
        )
        stores.task.create_task(project="myapp", title="Code task", task_type="dev")
        tasks = stores.task.list_tasks("myapp")
        result = await call(mcp, "pm_agent_suggest", project="myapp", task_id=tasks[0].id)
        assert "Recommended model: small" in result

    async def test_suggest_no_model_when_not_configured(self, setup):
        mcp, stores, _ = setup
        stores.task.create_task(project="myapp", title="Code task", task_type="dev")
        tasks = stores.task.list_tasks("myapp")
        result = await call(mcp, "pm_agent_suggest", project="myapp", task_id=tasks[0].id)
        assert "Recommended model" not in result
