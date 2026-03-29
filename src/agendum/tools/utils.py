"""Utility tools: dependency checking."""

from __future__ import annotations

from agendum.task_graph import detect_cycles, find_unblocked_tasks


def register(mcp, stores, agents):
    """Register utility tools on the MCP server."""

    @mcp.tool()
    def pm_check_deps(project: str) -> str:
        """Check for dependency cycles and show which tasks are ready to start.

        Use this to diagnose blocked workflows or validate task dependencies
        before starting work.
        """
        try:
            all_tasks = stores.task.list_tasks(project)
        except ValueError as e:
            return f"Error: {e}"
        cycles = detect_cycles(all_tasks)

        lines = [f"Dependency check for '{project}':"]
        lines.append(f"Total tasks: {len(all_tasks)}")

        unblocked = find_unblocked_tasks(all_tasks)
        lines.append(f"Ready to start: {len(unblocked)}")
        for t in unblocked:
            lines.append(f"  - {t.id}: {t.title}")

        if cycles:
            lines.append(f"\nCYCLES DETECTED ({len(cycles)}):")
            for cycle in cycles:
                lines.append(f"  {' -> '.join(cycle)}")
        else:
            lines.append("No dependency cycles found.")

        return "\n".join(lines)
