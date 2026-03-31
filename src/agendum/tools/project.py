"""Project management tools: create, list, get, update spec/plan."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from agendum.models import Agent


def register(mcp: FastMCP, stores: Any, agents: dict[str, Agent]) -> None:
    """Register project tools on the MCP server."""

    @mcp.tool()
    def pm_project_create(name: str, description: str = "") -> str:
        """Create a new project with spec.md, plan.md, and tasks/ directory.

        The spec.md is a living specification you should update as requirements
        evolve. The plan.md tracks the task decomposition strategy.
        """
        try:
            stores.project.create_project(name, description)
        except ValueError as e:
            return f"Error: {e}"
        return f"Created project '{name}'. Edit spec.md to define requirements."

    @mcp.tool()
    def pm_project_list() -> str:
        """List all projects in this agendum board."""
        projects = stores.project.list_projects()
        if not projects:
            return "No projects yet. Use pm_project_create to create one."
        return "Projects:\n" + "\n".join(f"  - {p}" for p in projects)

    @mcp.tool()
    def pm_project_get(project: str) -> str:
        """Get a project's full spec and plan. Use this to understand what a project is about."""
        try:
            p = stores.project.get_project(project)
        except ValueError as e:
            return f"Error: {e}"
        if not p:
            return f"Error: project '{project}' not found."
        return f"# Project: {p.name}\n\n## Spec\n{p.spec}\n\n## Plan\n{p.plan}"

    @mcp.tool()
    def pm_project_spec_update(project: str, content: str) -> str:
        """Update a project's spec.md (living specification).

        The spec should contain requirements, design decisions, and acceptance
        criteria. Update it as you learn more about what needs to be built.
        """
        try:
            stores.project.update_spec(project, content)
        except (ValueError, FileNotFoundError) as e:
            return f"Error: {e}"
        return f"Updated spec for '{project}'."

    @mcp.tool()
    def pm_project_plan_update(project: str, content: str) -> str:
        """Update a project's plan.md (task decomposition strategy).

        The plan should outline how the spec will be implemented — what tasks
        exist, their order, and dependencies.
        """
        try:
            stores.project.update_plan(project, content)
        except (ValueError, FileNotFoundError) as e:
            return f"Error: {e}"
        return f"Updated plan for '{project}'."
