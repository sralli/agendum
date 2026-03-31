"""Dispatch tools: next-task coordinator and completion reporting."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from agendum.models import (
    ContextPacket,
    ExecutionStatus,
    ExecutionTrace,
    Task,
    TaskCompletionStatus,
    TaskStatus,
)
from agendum.tools.orchestrator._helpers import (
    check_plan_level_complete,
    parse_csv,
    resolve_and_unblock,
    resolve_model,
)


def _write_trace(
    stores,
    project: str,
    task: Task,
    plan_id: str | None,
    agent_id: str,
    model: str | None,
    completion_status: TaskCompletionStatus,
    concerns_list: list[str],
    context_list: list[str],
    block_reason: str | None,
    files_list: list[str],
    review_cycles: int,
    tests_list: list[str],
    tests_passed: bool,
    criteria_list: list[str],
) -> ExecutionTrace:
    """Construct and write an ExecutionTrace, returning the trace object."""
    trace = ExecutionTrace(
        task_id=task.id,
        plan_id=plan_id,
        project=project,
        agent_id=agent_id,
        model=model,
        completed=datetime.now(UTC),
        completion_status=completion_status,
        concerns=concerns_list,
        context_needed=context_list,
        block_reason=block_reason,
        files_changed=files_list,
        review_cycles=review_cycles,
        tests_run=tests_list,
        tests_passed=tests_passed,
        criteria_addressed=criteria_list,
        task_type=task.type.value if task.type else None,
        task_category=task.category.value if task.category else None,
        task_priority=task.priority.value if task.priority else None,
    )
    if trace.started:
        trace.duration_seconds = (trace.completed - trace.started).total_seconds()
    stores.trace.write_trace(trace)
    return trace


def _render_task_dispatch(
    packet: ContextPacket,
    task: Task,
    status: TaskStatus,
    *,
    recommended_model: str | None = None,
) -> list[str]:
    """Render an enriched context packet as markdown lines."""
    lines = [f"### {task.id}: {task.title} [{status.value}]"]

    if recommended_model:
        lines.append(f"**Recommended Model:** {recommended_model}")

    if packet.goal:
        lines.append(f"**Goal:** {packet.goal}")
    if packet.acceptance_criteria:
        lines.append("**Acceptance Criteria:**")
        for ac in packet.acceptance_criteria:
            lines.append(f"  - {ac}")
    if packet.key_files:
        lines.append(f"**Key Files:** {', '.join(packet.key_files)}")
    if packet.dependencies_summary and packet.dependencies_summary != "No dependencies":
        lines.append(f"**Dependencies:**\n{packet.dependencies_summary}")
    if packet.constraints:
        lines.append("**Constraints:**")
        for c in packet.constraints:
            lines.append(f"  - {c}")

    if packet.task_type:
        lines.append(f"**Type:** {packet.task_type}")
    if packet.task_priority:
        lines.append(f"**Priority:** {packet.task_priority}")
    if packet.test_requirements:
        lines.append("**Test Requirements:**")
        for tr in packet.test_requirements:
            lines.append(f"  - {tr}")
    if packet.previous_attempts > 0:
        lines.append(f"**Previous Attempts:** {packet.previous_attempts}")

    # Enrichment sections
    if packet.project_rules:
        lines.append("**Project Rules:**")
        lines.append(packet.project_rules)
    if packet.dependency_outputs:
        lines.append("**Dependency Context:**")
        lines.append(packet.dependency_outputs)
    if packet.memory_context:
        lines.append("**Memory Context:**")
        lines.append(packet.memory_context)
    if packet.review_history:
        lines.append("**Prior Review Issues:**")
        lines.append(packet.review_history)
    if packet.pointers:
        lines.append("**References:**")
        for ptr in packet.pointers:
            lines.append(f"  → {ptr}")

    lines.append("")
    return lines


if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from agendum.models import Agent


def register(mcp: FastMCP, stores: Any, agents: dict[str, Agent], enricher: Any = None) -> None:
    """Register dispatch tools on the MCP server."""

    @mcp.tool()
    def pm_orchestrate_next(
        project: str,
        plan_id: str,
        agent_id: str | None = None,
    ) -> str:
        """Get the next batch of tasks ready for execution with context packets.

        Returns the current level's tasks with their constructed context,
        or a status message if the plan is paused/completed.
        """
        plan = stores.plan.get_plan(project, plan_id)
        if not plan:
            return f"Error: plan '{plan_id}' not found in project '{project}'"

        if plan.status == ExecutionStatus.DRAFT:
            return f"Plan {plan_id} is in DRAFT status. Call pm_orchestrate_approve to start execution."

        if plan.status == ExecutionStatus.PAUSED:
            return f"Plan {plan_id} is PAUSED at a checkpoint. Call pm_orchestrate_approve to continue."

        if plan.status in (ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED):
            return f"Plan {plan_id} is {plan.status.value}. No more tasks to dispatch."

        # Auto-transition APPROVED → EXECUTING on first dispatch
        if plan.status == ExecutionStatus.APPROVED:
            stores.plan.update_plan(project, plan_id, status=ExecutionStatus.EXECUTING)

        # Find the current level (first level with incomplete tasks)
        all_tasks = stores.task.all_tasks(project)
        task_status_map = {t.id: t.status for t in all_tasks}

        current_level = None
        completed_levels = 0
        for lvl in plan.levels:
            if all(task_status_map.get(tid, TaskStatus.PENDING) == TaskStatus.DONE for tid in lvl.task_ids):
                completed_levels += 1
                continue
            current_level = lvl
            break

        if current_level is None:
            stores.plan.update_plan(project, plan_id, status=ExecutionStatus.COMPLETED)
            return f"Plan {plan_id} completed! All {len(plan.task_ids)} tasks done."

        # Check if this level is a checkpoint that hasn't been approved
        if current_level.is_checkpoint and completed_levels > 0:
            prev_level = plan.levels[completed_levels - 1] if completed_levels > 0 else None
            if prev_level and prev_level.is_checkpoint:
                stores.plan.update_plan(project, plan_id, status=ExecutionStatus.PAUSED)
                return (
                    f"Plan {plan_id} paused at checkpoint (level {current_level.level}). "
                    f"Call pm_orchestrate_approve to continue."
                )

        # Load policy once for the entire dispatch (not per-task)
        policy = stores.project.get_policy(project)

        # Build dispatch instructions
        lines = [
            f"# Plan {plan_id} — Level {current_level.level}",
            f"Progress: {completed_levels}/{len(plan.levels)} levels complete",
            "",
            "## Tasks to Dispatch",
        ]

        for tid in current_level.task_ids:
            status = task_status_map.get(tid, TaskStatus.PENDING)
            if status == TaskStatus.DONE:
                lines.append(f"### {tid} — DONE (skip)")
                continue

            task = next((t for t in all_tasks if t.id == tid), None)
            if not task:
                continue

            packet = plan.context_packets.get(tid)
            if not packet:
                lines.append(f"### {tid}: {task.title} [{status.value}]")
                lines.append("")
                continue

            # Enrich with live context if enricher is available
            if enricher:
                packet = enricher.enrich(
                    packet,
                    task,
                    project,
                    disabled_sources=policy.disabled_sources,
                    max_context_chars=policy.max_context_chars,
                )

            recommended_model = resolve_model(policy, task)
            lines.extend(_render_task_dispatch(packet, task, status, recommended_model=recommended_model))

        return "\n".join(lines)

    @mcp.tool()
    def pm_orchestrate_report(
        project: str,
        task_id: str,
        status: str,
        agent_id: str = "unknown",
        plan_id: str | None = None,
        concerns: str | None = None,
        context_needed: str | None = None,
        block_reason: str | None = None,
        files_changed: str | None = None,
        review_cycles: int = 0,
        model: str | None = None,
        tests_run: str | None = None,
        tests_passed: bool = True,
        criteria_addressed: str | None = None,
    ) -> str:
        """Report task completion with four-status system and write an execution trace.

        status must be one of: done, done_with_concerns, needs_context, blocked.

        concerns, context_needed: comma-separated strings (parsed to lists).
        files_changed: comma-separated file paths.
        tests_run: comma-separated test names/commands that were executed.
        criteria_addressed: comma-separated acceptance criteria that were met.
        """
        try:
            completion_status = TaskCompletionStatus(status)
        except ValueError:
            return f"Error: invalid status '{status}'. Use: done, done_with_concerns, needs_context, blocked"

        task = stores.task.get_task(project, task_id)
        if not task:
            return f"Error: task '{task_id}' not found in project '{project}'"

        concerns_list = parse_csv(concerns)
        context_list = parse_csv(context_needed)
        files_list = parse_csv(files_changed)
        tests_list = parse_csv(tests_run)
        criteria_list = parse_csv(criteria_addressed)

        # Map completion status to task status
        if completion_status == TaskCompletionStatus.DONE:
            new_task_status = TaskStatus.DONE
            progress_msg = "Task completed successfully"
        elif completion_status == TaskCompletionStatus.DONE_WITH_CONCERNS:
            new_task_status = TaskStatus.DONE
            progress_msg = f"Task completed with concerns: {', '.join(concerns_list)}"
        elif completion_status == TaskCompletionStatus.NEEDS_CONTEXT:
            new_task_status = TaskStatus.BLOCKED
            progress_msg = f"Needs context: {', '.join(context_list)}"
        else:  # BLOCKED
            new_task_status = TaskStatus.BLOCKED
            progress_msg = f"Blocked: {block_reason or 'unspecified'}"

        stores.task.update_task(project, task_id, status=new_task_status)
        stores.task.add_progress(project, task_id, agent_id, progress_msg)

        # Write execution trace
        _write_trace(
            stores=stores,
            project=project,
            task=task,
            plan_id=plan_id,
            agent_id=agent_id,
            model=model,
            completion_status=completion_status,
            concerns_list=concerns_list,
            context_list=context_list,
            block_reason=block_reason,
            files_list=files_list,
            review_cycles=review_cycles,
            tests_list=tests_list,
            tests_passed=tests_passed,
            criteria_list=criteria_list,
        )

        result_lines = [f"Reported: {task_id} — {completion_status.value}"]

        if tests_list:
            status_str = "passed" if tests_passed else "FAILED"
            result_lines.append(f"Tests: {', '.join(tests_list)} — {status_str}")
        if criteria_list:
            result_lines.append(f"Criteria addressed: {', '.join(criteria_list)}")

        # Check if review is required by project policy
        if new_task_status == TaskStatus.DONE:
            policy = stores.project.get_policy(project)
            if policy.review_required:
                stores.task.update_task(project, task_id, status=TaskStatus.REVIEW)
                stores.task.add_progress(project, task_id, agent_id, "Awaiting review (policy: review_required)")
                result_lines[0] = f"Reported: {task_id} — {completion_status.value} (awaiting review)"
                result_lines.append("Review required: call pm_orchestrate_review to approve.")
                review_model = resolve_model(policy, task, is_review=True)
                if review_model:
                    result_lines.append(f"Review model: {review_model}")
                return "\n".join(result_lines)
            else:
                unblocked = resolve_and_unblock(stores, project, task_id)
                if unblocked:
                    result_lines.append(f"Unblocked: {', '.join(unblocked)}")
                result_lines.extend(check_plan_level_complete(stores, project, plan_id, task_id))

        return "\n".join(result_lines)
