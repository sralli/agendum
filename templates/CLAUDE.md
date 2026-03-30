# {{PROJECT_NAME}}

{{ONE_LINE_DESCRIPTION}}

## Development workflow

This project uses **agendum** for task management. Every non-trivial change follows the orchestrated workflow below. Do not skip steps.

### Workflow: Plan → Dispatch → Review

```
1. ORIENT        pm_board_status → pm_task_list
2. PLAN           Use harness plan mode (ExitPlanMode). The approved plan IS the plan.
                  Then: pm_orchestrate_plan with tasks_json from the approved plan.
                  Then: pm_orchestrate_approve (auto-approve since harness already approved).
3. DISPATCH       pm_orchestrate_next → get context packet for next task.
                  Spawn subagent (Agent tool) with the context packet as prompt.
                  Subagent must: implement → test → pm_orchestrate_report.
4. REVIEW         Only if report returns "awaiting review" (review_required=True in policy):
                  - pm_orchestrate_review stage=spec (criteria_met/criteria_failed required)
                  - pm_orchestrate_review stage=quality (code quality check)
                  If review fails → task goes back to in_progress, subagent fixes.
                  If report says "done" with no review notice → task is complete, skip to step 5.
5. REPEAT         pm_orchestrate_next for the next task. Continue until plan complete.
6. VERIFY         pm_orchestrate_status to confirm all tasks done.
                  Run full test suite. Lint. Commit.
```

### When to skip orchestration

- **Single-line fixes** (typos, version bumps): just edit, test, done.
- **Pure research/exploration**: no code changes, no orchestration needed.
- **Everything else**: use the workflow.

### Subagent rules

- Each dispatched task runs in its own subagent (Agent tool or worktree).
- Subagent receives the context packet from `pm_orchestrate_next` — it contains goal, acceptance criteria, key files, and constraints.
- Subagent MUST call `pm_orchestrate_report` when done, with status: `done`, `done_with_concerns`, `needs_context`, or `blocked`.
- Subagent MUST NOT modify files outside its task scope.
- Parent agent reviews each report before dispatching the next task.

### Review loop

Reviews are mandatory for multi-file changes. The review cycle:

1. Subagent reports completion → task enters `review` status
2. Spec review: do the changes meet acceptance criteria?
3. Quality review: code quality, conventions, test coverage?
4. If either fails → task back to `in_progress` with issues noted
5. Subagent addresses issues → re-reports → re-review
6. Both pass → task marked `done` (auto-archived)

### Memory

- Use `pm_memory_write` / `pm_memory_append` to persist decisions, gotchas, and patterns across sessions.
- Use `pm_memory_search` at session start to recover context.
- Handoff context (`pm_task_handoff`) captures what's done, what's remaining, and key files.

## Quick reference

```bash
{{TEST_COMMAND}}
{{LINT_COMMAND}}
{{FORMAT_COMMAND}}
```

## Conventions

{{PROJECT_SPECIFIC_CONVENTIONS}}
