"""Board-level tools: init and status overview."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from agendum.models import TaskStatus

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from agendum.models import Agent


def register(mcp: FastMCP, stores: Any, agents: dict[str, Agent]) -> None:
    """Register board tools on the MCP server."""

    @mcp.tool()
    def pm_board_init(name: str = "agendum") -> str:
        """Initialize .agendum/ directory in the current project. Run this first.

        Creates the directory structure for projects, agents, and memory.
        Safe to re-run — will not overwrite existing data.
        """
        config = stores.project.init_board(name)
        return f"Initialized agendum board at {stores.root}. Config: {json.dumps(config.model_dump())}"

    @mcp.tool()
    def pm_board_status() -> str:
        """Get a dashboard overview of all projects.

        Shows: project list, task counts by status, blocked tasks,
        active agents, and recent activity. Use this to orient yourself
        at the start of a session.
        """
        projects = stores.project.list_projects()
        total = 0
        archived_total = 0
        by_status: dict[str, int] = {}
        blocked: list[str] = []
        recent: list[str] = []

        for proj in projects:
            tasks = stores.task.list_tasks(proj)
            archived = stores.task.list_archived_tasks(proj)
            total += len(tasks)
            archived_total += len(archived)
            for t in tasks:
                by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
                if t.status == TaskStatus.BLOCKED:
                    blocked.append(f"{t.id} ({t.title})")
                if t.progress:
                    last = t.progress[-1]
                    recent.append(f"[{last.timestamp.strftime('%m-%d %H:%M')}] {t.id}: {last.message}")
            for t in archived:
                by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

        recent.sort(reverse=True)
        active = [a.id for a in agents.values() if a.status == "active"]

        lines = [
            "# Board Status",
            f"Projects: {', '.join(projects) or 'none'}",
            f"Total tasks: {total} active, {archived_total} archived",
            f"By status: {json.dumps(by_status)}",
            f"Blocked: {', '.join(blocked) or 'none'}",
            f"Active agents: {', '.join(active) or 'none'}",
            "Recent activity (last 5):",
        ]
        for r in recent[:5]:
            lines.append(f"  {r}")

        return "\n".join(lines)
