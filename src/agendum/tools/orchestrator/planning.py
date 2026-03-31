"""Planning tools: create plans and view status."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from agendum.models import (
    ApprovalPolicy,
    ContextPacket,
    ExecutionLevel,
    ExecutionPlan,
    ExecutionStatus,
    TaskCompletionStatus,
    TaskStatus,
)
from agendum.task_graph import detect_cycles, topological_levels

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from agendum.models import Agent


def register(mcp: FastMCP, stores: Any, agents: dict[str, Agent]) -> None:
    """Register planning tools on the MCP server."""

    @mcp.tool()
    def pm_orchestrate_plan(
        project: str,
        goal: str,
        tasks_json: str,
        approval_policy: str = "auto_with_review",
        agent_id: str = "unknown",
        checkpoint_every: int = 0,
    ) -> str:
        """Create an execution plan from a structured task decomposition.

        Call this after the human has reviewed and approved the task decomposition
        (e.g., via Claude Code plan mode). Plans always start as DRAFT — call
        pm_orchestrate_approve to begin execution.

        tasks_json is a JSON array of objects, each with:
          - title (str, required)
          - description (str, optional)
          - type (str, optional: dev/docs/review/research/ops/planning)
          - priority (str, optional: critical/high/medium/low)
          - depends_on_indices (list[int], optional: indices into the array)
          - acceptance_criteria (list[str], optional)
          - key_files (list[str], optional)
          - constraints (list[str], optional)

        Creates tasks, computes topological levels, generates context packets,
        and writes an execution plan. Returns the plan summary.
        """
        try:
            task_defs = json.loads(tasks_json)
        except json.JSONDecodeError as e:
            return f"Error: invalid JSON — {e}"

        if not isinstance(task_defs, list) or not task_defs:
            return "Error: tasks_json must be a non-empty JSON array"

        try:
            policy = ApprovalPolicy(approval_policy)
        except ValueError:
            return f"Error: invalid approval_policy '{approval_policy}'. Use: human_required, auto_with_review, auto"

        proj = stores.project.get_project(project)
        if not proj:
            return f"Error: project '{project}' not found"

        # Create tasks
        created_tasks = []
        for i, td in enumerate(task_defs):
            title = td.get("title")
            if not title:
                return f"Error: task at index {i} missing 'title'"

            task = stores.task.create_task(
                project=project,
                title=title,
                context=td.get("description", ""),
                type=td.get("type", "dev"),
                priority=td.get("priority", "medium"),
                acceptance_criteria=td.get("acceptance_criteria", []),
                tags=td.get("tags", []),
            )
            created_tasks.append(task)

        # Resolve dependency indices to task IDs
        for i, td in enumerate(task_defs):
            dep_indices = td.get("depends_on_indices", [])
            if dep_indices:
                dep_ids = [created_tasks[idx].id for idx in dep_indices if 0 <= idx < len(created_tasks)]
                if dep_ids:
                    stores.task.update_task(project, created_tasks[i].id, depends_on=dep_ids)
                    created_tasks[i].depends_on = dep_ids

        # Cycle check
        cycles = detect_cycles(created_tasks)
        if cycles:
            cycle_str = ", ".join(" -> ".join(c) for c in cycles)
            return f"Error: dependency cycles detected: {cycle_str}"

        # Compute topological levels
        levels_data = topological_levels(created_tasks)
        levels = [
            ExecutionLevel(
                level=n,
                task_ids=tids,
                is_checkpoint=checkpoint_every > 0 and (n + 1) % checkpoint_every == 0,
            )
            for n, tids in enumerate(levels_data)
        ]

        # Build context packets
        task_map = {t.id: t for t in created_tasks}
        context_packets = {}
        for i, t in enumerate(created_tasks):
            td = task_defs[i]
            dep_summary = (
                "\n".join(f"- {d}: {task_map[d].title}" for d in t.depends_on if d in task_map) or "No dependencies"
            )

            context_packets[t.id] = ContextPacket(
                task_id=t.id,
                goal=t.title,
                acceptance_criteria=t.acceptance_criteria,
                key_files=td.get("key_files", [])[:10],
                dependencies_summary=dep_summary,
                constraints=td.get("constraints", []),
                task_type=t.type.value,
                task_priority=t.priority.value,
                test_requirements=t.test_requirements,
            )

        # Create the plan
        plan = ExecutionPlan(
            id="",
            project=project,
            goal=goal,
            status=ExecutionStatus.DRAFT,
            approval_policy=policy,
            task_ids=[t.id for t in created_tasks],
            levels=levels,
            context_packets=context_packets,
            created_by=agent_id,
        )
        plan = stores.plan.create_plan(plan)

        # Format response
        lines = [
            f"# Plan Created: {plan.id}",
            f"Project: {project}",
            f"Goal: {goal}",
            f"Status: {plan.status.value}",
            f"Policy: {plan.approval_policy.value}",
            f"Tasks: {len(created_tasks)}",
            f"Levels: {len(levels)}",
            "",
            "## Execution Levels",
        ]
        for lvl in levels:
            ckpt = " [CHECKPOINT]" if lvl.is_checkpoint else ""
            lines.append(f"Level {lvl.level}{ckpt}:")
            for tid in lvl.task_ids:
                t = task_map.get(tid)
                lines.append(f"  - {tid}: {t.title if t else '?'}")

        return "\n".join(lines)

    @mcp.tool()
    def pm_orchestrate_status(
        project: str,
        plan_id: str,
    ) -> str:
        """Get execution progress for a plan with per-level completion and metrics.

        Shows plan goal, status, level-by-level progress, and aggregate trace data.
        """
        plan = stores.plan.get_plan(project, plan_id)
        if not plan:
            return f"Error: plan '{plan_id}' not found in project '{project}'"

        all_tasks = stores.task.all_tasks(project)
        task_map = {t.id: t for t in all_tasks}

        lines = [
            f"# Plan: {plan.id}",
            f"**Goal:** {plan.goal}",
            f"**Status:** {plan.status.value}",
            f"**Policy:** {plan.approval_policy.value}",
            f"**Created by:** {plan.created_by}",
            f"**Tasks:** {len(plan.task_ids)}",
            "",
            "## Level Progress",
        ]

        total_done = 0
        for lvl in plan.levels:
            done_count = sum(1 for tid in lvl.task_ids if (t := task_map.get(tid)) and t.status == TaskStatus.DONE)
            total_done += done_count

            ckpt = " [CHECKPOINT]" if lvl.is_checkpoint else ""
            status_icon = "done" if done_count == len(lvl.task_ids) else f"{done_count}/{len(lvl.task_ids)}"
            lines.append(f"  Level {lvl.level}{ckpt}: {status_icon}")
            for tid in lvl.task_ids:
                t = task_map.get(tid)
                s = t.status.value if t else "?"
                lines.append(f"    - {tid}: {t.title if t else '?'} [{s}]")

        lines.append("")
        lines.append(f"**Overall:** {total_done}/{len(plan.task_ids)} tasks done")

        # Trace metrics
        traces = stores.trace.list_traces(project, plan_id=plan_id)
        if traces:
            lines.append("")
            lines.append("## Trace Metrics")
            durations = [t.duration_seconds for t in traces if t.duration_seconds]
            if durations:
                lines.append(f"  Avg duration: {sum(durations) / len(durations):.0f}s")
            concerns = [c for t in traces for c in t.concerns]
            if concerns:
                lines.append(f"  Concerns: {len(concerns)}")
                for c in concerns[:5]:
                    lines.append(f"    - {c}")
            blocked = [t for t in traces if t.completion_status == TaskCompletionStatus.BLOCKED]
            if blocked:
                lines.append(f"  Blocked attempts: {len(blocked)}")

        return "\n".join(lines)
