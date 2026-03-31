"""Policy tools: view and update project orchestration policy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agendum.models import ApprovalPolicy

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
    ) -> str:
        """View or update a project's orchestration policy.

        Call with no optional args to view current policy.
        Pass any arg to update it.
        """
        proj = stores.project.get_project(project)
        if not proj:
            return f"Error: project '{project}' not found"

        updates = {}
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
        ]
        return "\n".join(lines)
