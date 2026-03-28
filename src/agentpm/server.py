"""agentpm MCP server — exposes pm.* tools for any MCP-capable agent."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agentpm.deps import (
    detect_cycles,
    find_unblocked_tasks,
    resolve_completions,
    suggest_next_task,
)
from agentpm.models import Agent, TaskStatus
from agentpm.store.memory_store import MemoryStore
from agentpm.store.project_store import ProjectStore
from agentpm.store.task_store import TaskStore

# Resolve .agentpm root directory
_ROOT_ENV = os.environ.get("AGENTPM_ROOT")
if _ROOT_ENV:
    AGENTPM_ROOT = Path(_ROOT_ENV)
elif os.environ.get("AGENTPM_HOME"):
    AGENTPM_ROOT = Path.home() / ".agentpm"
else:
    # Default: .agentpm in current working directory
    AGENTPM_ROOT = Path.cwd() / ".agentpm"

# Stores
task_store = TaskStore(AGENTPM_ROOT)
project_store = ProjectStore(AGENTPM_ROOT)
memory_store = MemoryStore(AGENTPM_ROOT)

# In-memory agent registry (agents re-register each session)
_agents: dict[str, Agent] = {}

# MCP Server
mcp = FastMCP(
    "agentpm",
    instructions=(
        "agentpm is a universal project management system for AI coding agents. "
        "Use pm.* tools to manage projects, tasks, memory, and agent coordination. "
        "Tasks are stored as Markdown files with YAML frontmatter in .agentpm/. "
        "Start with pm_board_init to initialize, then pm_project_create to create a project."
    ),
)


# ─── Board Tools ───


@mcp.tool()
def pm_board_init(name: str = "agentpm") -> str:
    """Initialize .agentpm/ directory in the current project. Run this first."""
    config = project_store.init_board(name)
    return f"Initialized agentpm board at {AGENTPM_ROOT}. Config: {json.dumps(config.model_dump())}"


@mcp.tool()
def pm_board_status() -> str:
    """Get overview of all projects: task counts by status, blocked tasks, active agents."""
    projects = project_store.list_projects()
    total = 0
    by_status: dict[str, int] = {}
    blocked: list[str] = []
    recent: list[str] = []

    for proj in projects:
        tasks = task_store.list_tasks(proj)
        total += len(tasks)
        for t in tasks:
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
            if t.status == TaskStatus.BLOCKED:
                blocked.append(f"{t.id} ({t.title})")
            if t.progress:
                last = t.progress[-1]
                recent.append(f"[{last.timestamp.strftime('%m-%d %H:%M')}] {t.id}: {last.message}")

    recent.sort(reverse=True)
    active = [a.id for a in _agents.values() if a.status == "active"]

    lines = [
        f"# Board Status",
        f"Projects: {', '.join(projects) or 'none'}",
        f"Total tasks: {total}",
        f"By status: {json.dumps(by_status)}",
        f"Blocked: {', '.join(blocked) or 'none'}",
        f"Active agents: {', '.join(active) or 'none'}",
        f"Recent activity (last 5):",
    ]
    for r in recent[:5]:
        lines.append(f"  {r}")

    return "\n".join(lines)


# ─── Project Tools ───


@mcp.tool()
def pm_project_create(name: str, description: str = "") -> str:
    """Create a new project with spec.md, plan.md, and tasks/ directory."""
    project = project_store.create_project(name, description)
    return f"Created project '{name}' at {AGENTPM_ROOT}/projects/{name}/. Edit spec.md to define requirements."


@mcp.tool()
def pm_project_list() -> str:
    """List all projects."""
    projects = project_store.list_projects()
    if not projects:
        return "No projects yet. Use pm_project_create to create one."
    return "Projects:\n" + "\n".join(f"  - {p}" for p in projects)


@mcp.tool()
def pm_project_get(project: str) -> str:
    """Get project details including spec and plan."""
    p = project_store.get_project(project)
    if not p:
        return f"Project '{project}' not found."
    return f"# Project: {p.name}\n\n## Spec\n{p.spec}\n\n## Plan\n{p.plan}"


@mcp.tool()
def pm_spec_update(project: str, content: str) -> str:
    """Update a project's spec.md (living specification)."""
    project_store.update_spec(project, content)
    return f"Updated spec for '{project}'."


@mcp.tool()
def pm_plan_update(project: str, content: str) -> str:
    """Update a project's plan.md."""
    project_store.update_plan(project, content)
    return f"Updated plan for '{project}'."


# ─── Task Tools ───


@mcp.tool()
def pm_task_create(
    project: str,
    title: str,
    description: str = "",
    priority: str = "medium",
    task_type: str = "dev",
    depends_on: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """Create a new task in a project."""
    task = task_store.create_task(
        project=project,
        title=title,
        context=description,
        priority=priority,
        type=task_type,
        depends_on=depends_on or [],
        acceptance_criteria=acceptance_criteria or [],
        tags=tags or [],
    )
    status_note = ""
    if task.depends_on:
        status_note = f" (blocked by: {', '.join(task.depends_on)})"
    return f"Created task {task.id}: {task.title}{status_note}"


@mcp.tool()
def pm_task_list(
    project: str,
    status: str | None = None,
    assigned: str | None = None,
    tag: str | None = None,
    task_type: str | None = None,
) -> str:
    """List tasks in a project with optional filters."""
    status_enum = TaskStatus(status) if status else None
    tasks = task_store.list_tasks(project, status=status_enum, assigned=assigned, tag=tag, task_type=task_type)

    if not tasks:
        return f"No tasks found in '{project}' with the given filters."

    lines = [f"Tasks in '{project}' ({len(tasks)}):"]
    for t in tasks:
        assigned_str = f" [{t.assigned}]" if t.assigned else ""
        deps_str = f" (depends: {','.join(t.depends_on)})" if t.depends_on else ""
        lines.append(f"  [{t.status.value:^11}] {t.id}: {t.title} ({t.priority.value}){assigned_str}{deps_str}")
    return "\n".join(lines)


@mcp.tool()
def pm_task_get(project: str, task_id: str) -> str:
    """Get full details of a specific task."""
    task = task_store.get_task(project, task_id)
    if not task:
        return f"Task '{task_id}' not found in project '{project}'."

    lines = [
        f"# {task.title}",
        f"ID: {task.id} | Status: {task.status.value} | Priority: {task.priority.value}",
        f"Type: {task.type.value} | Assigned: {task.assigned or 'unassigned'}",
    ]
    if task.depends_on:
        lines.append(f"Depends on: {', '.join(task.depends_on)}")
    if task.blocks:
        lines.append(f"Blocks: {', '.join(task.blocks)}")
    if task.acceptance_criteria:
        lines.append("\n## Acceptance Criteria")
        for ac in task.acceptance_criteria:
            lines.append(f"  - [ ] {ac}")
    if task.context:
        lines.append(f"\n## Context\n{task.context}")
    if task.progress:
        lines.append("\n## Progress")
        for p in task.progress:
            lines.append(f"  - [{p.timestamp.strftime('%m-%d %H:%M')}] {p.agent} — {p.message}")
    if task.decisions:
        lines.append("\n## Decisions")
        for d in task.decisions:
            lines.append(f"  - {d}")
    if task.handoff:
        lines.append(f"\n## Handoff\n{task.handoff}")

    return "\n".join(lines)


@mcp.tool()
def pm_task_claim(project: str, task_id: str, agent_id: str) -> str:
    """Claim a pending task. Sets assigned agent and status to in_progress."""
    task = task_store.get_task(project, task_id)
    if not task:
        return f"Task '{task_id}' not found."
    if task.status not in (TaskStatus.PENDING, TaskStatus.BLOCKED):
        return f"Task '{task_id}' is {task.status.value}, cannot claim."

    # Check if dependencies are met
    all_tasks = task_store.list_tasks(project)
    done_ids = {t.id for t in all_tasks if t.status == TaskStatus.DONE}
    unmet = [d for d in task.depends_on if d not in done_ids]
    if unmet:
        return f"Cannot claim '{task_id}': unmet dependencies: {', '.join(unmet)}"

    task_store.update_task(project, task_id, assigned=agent_id, status=TaskStatus.IN_PROGRESS)
    task_store.add_progress(project, task_id, agent_id, "Claimed task")

    # Update agent registry
    if agent_id in _agents:
        _agents[agent_id].current_task = task_id

    return f"Claimed {task_id} for agent '{agent_id}'. Status: in_progress."


@mcp.tool()
def pm_task_update(project: str, task_id: str, message: str, agent_id: str = "unknown") -> str:
    """Add a progress update to a task."""
    task = task_store.add_progress(project, task_id, agent_id, message)
    if not task:
        return f"Task '{task_id}' not found."
    return f"Updated {task_id}: {message}"


@mcp.tool()
def pm_task_complete(project: str, task_id: str, agent_id: str = "unknown") -> str:
    """Mark a task as done. Auto-unblocks dependent tasks."""
    task = task_store.get_task(project, task_id)
    if not task:
        return f"Task '{task_id}' not found."

    # Mark done
    task_store.update_task(project, task_id, status=TaskStatus.DONE)
    task_store.add_progress(project, task_id, agent_id, "Completed task")

    # Auto-unblock dependents
    all_tasks = task_store.list_tasks(project)
    unblocked = resolve_completions(all_tasks, task_id)
    for uid in unblocked:
        task_store.update_task(project, uid, status=TaskStatus.PENDING)
        task_store.add_progress(project, uid, "system", f"Auto-unblocked: dependency {task_id} completed")

    result = f"Completed {task_id}."
    if unblocked:
        result += f" Unblocked: {', '.join(unblocked)}"
    return result


@mcp.tool()
def pm_task_block(project: str, task_id: str, reason: str, agent_id: str = "unknown") -> str:
    """Mark a task as blocked with a reason."""
    task_store.update_task(project, task_id, status=TaskStatus.BLOCKED)
    task_store.add_progress(project, task_id, agent_id, f"Blocked: {reason}")
    return f"Blocked {task_id}: {reason}"


@mcp.tool()
def pm_task_handoff(project: str, task_id: str, handoff_context: str, agent_id: str = "unknown") -> str:
    """Write handoff context for the next agent picking up this task."""
    task_store.update_task(project, task_id, handoff=handoff_context)
    task_store.add_progress(project, task_id, agent_id, "Wrote handoff context")
    return f"Handoff context saved for {task_id}."


@mcp.tool()
def pm_task_next(project: str, agent_type: str | None = None, preferred_types: str | None = None) -> str:
    """Suggest the best next task to work on based on priority and dependencies."""
    all_tasks = task_store.list_tasks(project)
    type_list = preferred_types.split(",") if preferred_types else None
    task = suggest_next_task(all_tasks, agent_type=agent_type, preferred_types=type_list)

    if not task:
        # Check if there are blocked or in-progress tasks
        in_progress = [t for t in all_tasks if t.status == TaskStatus.IN_PROGRESS]
        blocked = [t for t in all_tasks if t.status == TaskStatus.BLOCKED]
        if in_progress:
            return f"No pending tasks available. {len(in_progress)} task(s) in progress."
        if blocked:
            return f"No pending tasks. {len(blocked)} task(s) blocked."
        return "No tasks available. All done or no tasks created yet."

    deps_str = f" (after: {','.join(task.depends_on)})" if task.depends_on else ""
    return (
        f"Suggested next task:\n"
        f"  {task.id}: {task.title}\n"
        f"  Priority: {task.priority.value} | Type: {task.type.value}{deps_str}\n"
        f"  Context: {task.context[:200] if task.context else 'none'}\n"
        f"\nUse pm_task_claim to start working on it."
    )


# ─── Memory Tools ───


@mcp.tool()
def pm_memory_read(scope: str = "project") -> str:
    """Read a memory scope (project, decisions, or patterns)."""
    content = memory_store.read(scope)
    if not content:
        return f"Memory scope '{scope}' is empty."
    return f"# Memory: {scope}\n\n{content}"


@mcp.tool()
def pm_memory_write(scope: str, content: str) -> str:
    """Write/overwrite a memory scope."""
    memory_store.write(scope, content)
    return f"Memory '{scope}' updated."


@mcp.tool()
def pm_memory_append(scope: str, entry: str, author: str = "unknown") -> str:
    """Append an entry to a memory scope."""
    memory_store.append(scope, entry, author)
    return f"Appended to memory '{scope}'."


@mcp.tool()
def pm_memory_search(query: str) -> str:
    """Search across all memory scopes for matching content."""
    results = memory_store.search(query)
    if not results:
        return f"No matches found for '{query}'."

    lines = [f"Search results for '{query}':"]
    for scope, matches in results.items():
        lines.append(f"\n## {scope}")
        for m in matches[:5]:
            lines.append(f"  {m}")
    return "\n".join(lines)


# ─── Agent Tools ───


@mcp.tool()
def pm_agent_register(
    agent_id: str,
    agent_type: str = "unknown",
    capabilities: str = "",
    model: str | None = None,
) -> str:
    """Register an agent identity with capabilities."""
    caps = [c.strip() for c in capabilities.split(",") if c.strip()] if capabilities else []
    agent = Agent(
        id=agent_id,
        type=agent_type,
        capabilities=caps,
        model=model,
    )
    _agents[agent_id] = agent
    return f"Registered agent '{agent_id}' ({agent_type}). Capabilities: {caps}"


@mcp.tool()
def pm_agent_heartbeat(agent_id: str) -> str:
    """Signal that an agent is still active."""
    if agent_id not in _agents:
        return f"Agent '{agent_id}' not registered. Use pm_agent_register first."
    _agents[agent_id].last_heartbeat = datetime.now(timezone.utc)
    _agents[agent_id].status = "active"
    return f"Heartbeat recorded for '{agent_id}'."


@mcp.tool()
def pm_agent_list() -> str:
    """List all registered agents and their status."""
    if not _agents:
        return "No agents registered."

    lines = ["Registered agents:"]
    for a in _agents.values():
        task_str = f" working on {a.current_task}" if a.current_task else ""
        lines.append(f"  {a.id} ({a.type}) — {a.status}{task_str}")
    return "\n".join(lines)


# ─── Utility ───


@mcp.tool()
def pm_check_deps(project: str) -> str:
    """Check for dependency cycles and show dependency graph."""
    all_tasks = task_store.list_tasks(project)
    cycles = detect_cycles(all_tasks)

    lines = [f"Dependency check for '{project}':"]
    lines.append(f"Total tasks: {len(all_tasks)}")

    unblocked = find_unblocked_tasks(all_tasks)
    lines.append(f"Ready to start: {len(unblocked)}")
    for t in unblocked:
        lines.append(f"  - {t.id}: {t.title}")

    if cycles:
        lines.append(f"\n⚠ CYCLES DETECTED ({len(cycles)}):")
        for cycle in cycles:
            lines.append(f"  {' → '.join(cycle)}")
    else:
        lines.append("No dependency cycles found.")

    return "\n".join(lines)
