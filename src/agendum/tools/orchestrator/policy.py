"""Policy tools: view and update project orchestration policy."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from agendum.models import ApprovalPolicy, ModelRouting

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from agendum.models import Agent


def register(mcp: FastMCP, stores: Any, agents: dict[str, Agent]) -> None:
    """Register policy tools on the MCP server."""

    @mcp.tool()
    def pm_orchestrate_policy(
        project: str,
        approval_policy: str | None = None,
        review_required: bool | None = None,
        checkpoint_interval: int | None = None,
        max_parallel_tasks: int | None = None,
        model_default: str | None = None,
        model_review: str | None = None,
        model_by_category: str | dict | None = None,
        model_by_type: str | dict | None = None,
    ) -> str:
        """View or update a project's orchestration policy.

        Call with no optional args to view current policy.
        Pass any arg to update it.

        Model routing args configure which model tier to recommend for tasks:
          model_default: fallback tier for all tasks (e.g. "small")
          model_review: tier for review stages (e.g. "large")
          model_by_category: mapping of TaskCategory to tier
            (e.g. {"code-complex": "large", "docs": "fast"})
          model_by_type: mapping of TaskType to tier
            (e.g. {"dev": "small", "planning": "large"})
        """
        proj = stores.project.get_project(project)
        if not proj:
            return f"Error: project '{project}' not found"

        updates: dict[str, Any] = {}
        if approval_policy is not None:
            try:
                updates["approval_policy"] = ApprovalPolicy(approval_policy)
            except ValueError:
                return (
                    f"Error: invalid approval_policy '{approval_policy}'. Use: human_required, auto_with_review, auto"
                )
        if review_required is not None:
            updates["review_required"] = review_required
        if checkpoint_interval is not None:
            updates["checkpoint_interval"] = checkpoint_interval
        if max_parallel_tasks is not None:
            updates["max_parallel_tasks"] = max_parallel_tasks

        # Model routing updates — merge into existing routing
        model_updates: dict[str, Any] = {}
        if model_default is not None:
            model_updates["default"] = model_default or None
        if model_review is not None:
            model_updates["review"] = model_review or None
        if model_by_category is not None:
            if isinstance(model_by_category, dict):
                model_updates["by_category"] = model_by_category
            else:
                try:
                    model_updates["by_category"] = json.loads(model_by_category)
                except json.JSONDecodeError:
                    return "Error: model_by_category must be valid JSON (e.g. '{\"code-complex\": \"large\"}')"
        if model_by_type is not None:
            if isinstance(model_by_type, dict):
                model_updates["by_type"] = model_by_type
            else:
                try:
                    model_updates["by_type"] = json.loads(model_by_type)
                except json.JSONDecodeError:
                    return "Error: model_by_type must be valid JSON (e.g. '{\"dev\": \"small\"}')"

        if model_updates:
            current_policy = stores.project.get_policy(project)
            current_routing = current_policy.model_routing.model_dump()
            current_routing.update(model_updates)
            updates["model_routing"] = ModelRouting(**current_routing)

        if updates:
            policy = stores.project.update_policy(project, **updates)
        else:
            policy = stores.project.get_policy(project)

        lines = [
            f"# Policy: {project}",
            f"  approval_policy: {policy.approval_policy.value}",
            f"  review_required: {policy.review_required}",
            f"  checkpoint_interval: {policy.checkpoint_interval}",
            f"  max_parallel_tasks: {policy.max_parallel_tasks}",
            f"  model_routing.default: {policy.model_routing.default or '(none)'}",
            f"  model_routing.review: {policy.model_routing.review or '(none)'}",
        ]
        if policy.model_routing.by_category:
            lines.append(f"  model_routing.by_category: {policy.model_routing.by_category}")
        if policy.model_routing.by_type:
            lines.append(f"  model_routing.by_type: {policy.model_routing.by_type}")
        if policy.model_routing.by_task:
            lines.append(f"  model_routing.by_task: {policy.model_routing.by_task}")
        return "\n".join(lines)
