"""Plan store: manage execution plans for orchestrated workflows."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml

from agendum.models import ExecutionPlan
from agendum.store import sanitize_name
from agendum.store.locking import atomic_create, atomic_write, get_lock, next_sequential_id

logger = logging.getLogger(__name__)


class PlanStore:
    """File-based execution plan storage."""

    def __init__(self, root: Path):
        self.root = root

    def _plans_dir(self, project: str) -> Path:
        return self.root / "projects" / sanitize_name(project) / "plans"

    def _plan_path(self, project: str, plan_id: str) -> Path:
        return self._plans_dir(project) / f"{sanitize_name(plan_id)}.yaml"

    def _next_plan_id(self, project: str) -> str:
        """Generate next sequential plan ID like plan-001, plan-002."""
        return next_sequential_id(self._plans_dir(project), "plan", "yaml")

    def _load_plan(self, path: Path) -> ExecutionPlan:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return ExecutionPlan.model_validate(data)

    def create_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Create a new plan and write to disk."""
        plans_dir = self._plans_dir(plan.project)
        plans_dir.mkdir(parents=True, exist_ok=True)

        if not plan.id:
            plan.id = self._next_plan_id(plan.project)

        path = self._plan_path(plan.project, plan.id)

        # Atomic creation — fails if file already exists
        data = plan.model_dump(mode="json", exclude_none=True)
        try:
            atomic_create(path, yaml.dump(data, default_flow_style=False, sort_keys=False))
        except FileExistsError:
            raise ValueError(f"Plan '{plan.id}' already exists in project '{plan.project}'")

        return plan

    def get_plan(self, project: str, plan_id: str) -> ExecutionPlan | None:
        """Load a plan from disk."""
        path = self._plan_path(project, plan_id)
        if not path.exists():
            return None
        return self._load_plan(path)

    def update_plan(self, project: str, plan_id: str, **updates) -> ExecutionPlan | None:
        """Update plan fields and write back (locked + atomic)."""
        path = self._plan_path(project, plan_id)
        with get_lock(path):
            plan = self.get_plan(project, plan_id)
            if not plan:
                return None
            for key, value in updates.items():
                if hasattr(plan, key):
                    setattr(plan, key, value)
            plan.updated = datetime.now(UTC)
            data = plan.model_dump(mode="json", exclude_none=True)
            atomic_write(path, yaml.dump(data, default_flow_style=False, sort_keys=False))
        return plan

    def list_plans(self, project: str) -> list[ExecutionPlan]:
        """List all plans in a project."""
        plans_dir = self._plans_dir(project)
        if not plans_dir.exists():
            return []

        plans = []
        for path in sorted(plans_dir.glob("plan-*.yaml")):
            try:
                plans.append(self._load_plan(path))
            except Exception:
                logger.warning("Failed to parse plan file: %s", path)
                continue
        return plans
