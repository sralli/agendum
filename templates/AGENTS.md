# {{PROJECT_NAME}} — Agent Development Guide

> This file defines how AI agents work on this project. Read before making changes.

## Orchestrated workflow

This project uses **agendum** MCP tools for structured task management. Agents follow a mandatory pipeline for all non-trivial work.

### Pipeline overview

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐    ┌────────┐
│  Orient  │───▸│   Plan   │───▸│ Dispatch │───▸│ Report │───▸│ Review │
│          │    │          │    │          │    │        │    │        │
│ board    │    │ harness  │    │ next →   │    │ report │    │ spec + │
│ status   │    │ plan     │    │ subagent │    │ status │    │quality │
└─────────┘    │ approve  │    └──────────┘    └────────┘    └────────┘
               └──────────┘         │                            │
                                    │         ┌────────┐         │
                                    ◂─────────│  Fix   │◂────────┘
                                              │ issues │   (if failed)
                                              └────────┘
```

### Phase 1: Orient

At session start, run:
1. `pm_board_status` — see all projects, task counts, recent activity
2. `pm_memory_search` — recover decisions and context from prior sessions
3. `pm_task_list` on the relevant project — see pending work

### Phase 2: Plan

1. Use the harness plan mode (Claude Code `ExitPlanMode`, Cursor plan, etc.) to design the approach.
2. Once the human approves, translate the plan into agendum tasks:
   ```
   pm_orchestrate_plan(
     project="myproject",
     goal="...",
     tasks_json="[{title, description, depends_on_indices, acceptance_criteria, key_files}, ...]"
   )
   ```
3. Auto-approve since the harness already handled human review:
   ```
   pm_orchestrate_approve(project="myproject", plan_id="plan-001")
   ```

### Phase 3: Dispatch

For each task in the plan (respecting dependency order):

1. `pm_orchestrate_next(project, plan_id)` — get the next task + context packet
2. Spawn a subagent with the context packet:
   ```
   Agent(prompt="<context packet content>", subagent_type="general-purpose")
   ```
3. The subagent:
   - Reads the context packet (goal, acceptance criteria, key files, constraints)
   - Implements the change
   - Runs tests relevant to the change
   - Calls `pm_orchestrate_report(project, task_id, plan_id, status, ...)` when done

### Phase 4: Review

After each task report:

1. **Spec review** — check against acceptance criteria:
   ```
   pm_orchestrate_review(project, task_id, stage="spec", passed=true/false, issues="...")
   ```
2. **Quality review** — check code quality, conventions, coverage:
   ```
   pm_orchestrate_review(project, task_id, stage="quality", passed=true/false, issues="...")
   ```

If either review fails:
- Task returns to `in_progress`
- Issues are logged as progress entries
- Subagent (or new subagent) addresses the issues
- Re-reports → re-review

If both pass:
- Task marked `done` and auto-archived
- Dependents unblocked automatically

### Phase 5: Completion

1. `pm_orchestrate_status(project, plan_id)` — verify all tasks done
2. Run full test suite and lint
3. `pm_memory_write` — persist any decisions or gotchas learned
4. Commit

## Subagent contract

Subagents dispatched via the orchestrator MUST:

| Requirement | How |
|---|---|
| Stay scoped | Only modify files listed in context packet or directly related |
| Report back | Call `pm_orchestrate_report` with accurate status |
| Log progress | Use `pm_task_progress` for intermediate updates |
| Handle blockers | Report `blocked` status with clear reason, don't silently fail |
| Test changes | Run relevant tests before reporting `done` |

Subagents MUST NOT:
- Skip reporting (silent completion breaks the pipeline)
- Modify unrelated files (scope creep breaks review)
- Mark tasks done without testing

## Task lifecycle

```
pending → in_progress → review → done (auto-archived)
                ↑          │
                └──────────┘  (review failed)

pending → blocked (dependency unmet or external blocker)
              │
              └→ pending (auto-unblocked when dependency completes)
```

## When to skip orchestration

| Scenario | Orchestration? |
|---|---|
| Typo fix, version bump | No — just edit, test, commit |
| Single-file bug fix | No — but log with `pm_task_progress` if tracked |
| Multi-file feature | Yes — full pipeline |
| Refactor touching 3+ files | Yes — full pipeline |
| Research / exploration | No — but save findings to `pm_memory_write` |

## Memory and continuity

- `pm_memory_write(project, key, content)` — persist decisions, patterns, gotchas
- `pm_memory_append(project, key, content)` — add to existing memory
- `pm_memory_search(project, query)` — find relevant memories
- `pm_task_handoff(project, task_id, ...)` — structured handoff for incomplete tasks

Use memory for things that aren't obvious from code: "we chose X over Y because...", "this broke before when...", "the stakeholder wants...".

## Three-tier boundaries

### Always
{{ALWAYS_RULES}}

### Ask first
{{ASK_FIRST_RULES}}

### Never
{{NEVER_RULES}}
