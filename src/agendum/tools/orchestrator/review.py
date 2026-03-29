"""Review tools: two-stage review and plan approval."""

from __future__ import annotations

from agendum.models import ExecutionStatus, TaskStatus
from agendum.tools.orchestrator._helpers import (
    check_plan_level_complete,
    parse_csv,
    resolve_and_unblock,
)


def register(mcp, stores, agents):
    """Register review tools on the MCP server."""

    @mcp.tool()
    def pm_orchestrate_approve(
        project: str,
        plan_id: str,
        decision: str = "approve",
        agent_id: str = "unknown",
        notes: str = "",
    ) -> str:
        """Approve, reject, or modify an execution plan.

        decision: approve, reject, or modify.
        - approve: DRAFT -> EXECUTING, PAUSED -> EXECUTING
        - reject: -> CANCELLED
        - modify: -> DRAFT (for re-planning)

        In Claude Code: call this after ExitPlanMode when the human approves.
        """
        plan = stores.plan.get_plan(project, plan_id)
        if not plan:
            return f"Error: plan '{plan_id}' not found in project '{project}'"

        if plan.status not in (ExecutionStatus.DRAFT, ExecutionStatus.APPROVED, ExecutionStatus.PAUSED):
            return f"Error: plan is {plan.status.value}, not DRAFT/APPROVED/PAUSED. Cannot approve/reject."

        if decision == "approve":
            stores.plan.update_plan(project, plan_id, status=ExecutionStatus.EXECUTING)
            msg = f"Plan {plan_id} approved → executing"
        elif decision == "reject":
            stores.plan.update_plan(project, plan_id, status=ExecutionStatus.CANCELLED)
            msg = f"Plan {plan_id} rejected → cancelled"
        elif decision == "modify":
            stores.plan.update_plan(project, plan_id, status=ExecutionStatus.DRAFT)
            msg = f"Plan {plan_id} sent back to DRAFT for modification"
        else:
            return f"Error: invalid decision '{decision}'. Use: approve, reject, modify"

        if notes:
            msg += f"\nNotes: {notes}"

        return msg

    @mcp.tool()
    def pm_orchestrate_review(
        project: str,
        task_id: str,
        stage: str = "spec",
        passed: bool = True,
        reviewer_agent_id: str = "unknown",
        issues: str | None = None,
        plan_id: str | None = None,
    ) -> str:
        """Two-stage review for a completed task.

        stage: 'spec' (acceptance criteria compliance) or 'quality' (code quality).
        passed: True if review passed, False if failed.
        issues: comma-separated list of issues found.

        Flow:
        - Spec review fail -> task back to in_progress
        - Spec review pass -> ready for quality review
        - Quality review fail -> task back to in_progress
        - Quality review pass -> task marked DONE, dependents unblocked
        """
        task = stores.task.get_task(project, task_id)
        if not task:
            return f"Error: task '{task_id}' not found in project '{project}'"

        if task.status not in (TaskStatus.REVIEW, TaskStatus.DONE):
            return f"Error: task is {task.status.value}, not in review. Report completion first."

        if stage not in ("spec", "quality"):
            return f"Error: stage must be 'spec' or 'quality', got '{stage}'"

        issues_list = parse_csv(issues)

        if not passed:
            stores.task.update_task(project, task_id, status=TaskStatus.IN_PROGRESS)
            issue_str = f": {', '.join(issues_list)}" if issues_list else ""
            stores.task.add_progress(
                project,
                task_id,
                reviewer_agent_id,
                f"Review FAILED ({stage}){issue_str}",
            )

            # Record review failure as a new trace (append-only invariant)
            from agendum.models import ExecutionTrace, TaskCompletionStatus

            review_trace = ExecutionTrace(
                task_id=task_id,
                project=project,
                agent_id=reviewer_agent_id,
                completion_status=TaskCompletionStatus.BLOCKED,
                block_reason=f"Review failed ({stage}): {', '.join(issues_list)}",
                review_cycles=1,
                review_issues=issues_list,
            )
            stores.trace.write_trace(review_trace)

            issue_summary = ", ".join(issues_list) or "none specified"
            return f"Review failed ({stage}): {task_id} back to in_progress. Issues: {issue_summary}"

        # Passed
        if stage == "spec":
            stores.task.add_progress(
                project,
                task_id,
                reviewer_agent_id,
                "Spec review PASSED — acceptance criteria met",
            )
            return (
                f"Spec review passed for {task_id}. Proceed with quality review (pm_orchestrate_review stage=quality)."
            )

        # Quality review passed -> mark DONE and unblock
        stores.task.update_task(project, task_id, status=TaskStatus.DONE)
        stores.task.add_progress(
            project,
            task_id,
            reviewer_agent_id,
            "Quality review PASSED — task complete",
        )

        result_lines = [f"Quality review passed for {task_id} — marked DONE"]

        unblocked = resolve_and_unblock(stores, project, task_id)
        if unblocked:
            result_lines.append(f"Unblocked: {', '.join(unblocked)}")

        result_lines.extend(check_plan_level_complete(stores, project, plan_id, task_id))

        if issues_list:
            stores.task.add_progress(
                project,
                task_id,
                reviewer_agent_id,
                f"Quality notes: {', '.join(issues_list)}",
            )

        return "\n".join(result_lines)
