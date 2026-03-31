# agendum

Universal project management for AI coding agents. Python 3.13+, uv, FastMCP.

## Development workflow

This project uses its own **agendum** MCP tools for task management. Every non-trivial change follows the orchestrated workflow below.

### Workflow: Plan → Dispatch → Review

```
1. ORIENT        pm_board_status → pm_task_list project=agendum
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

- Each dispatched task runs in its own subagent.
- Subagent receives the context packet from `pm_orchestrate_next`.
- Subagent MUST call `pm_orchestrate_report` when done.
- Subagent MUST NOT modify files outside its task scope.
- Parent agent reviews each report before dispatching the next task.

## Quick reference

```bash
uv run pytest               # all tests must pass
uv run ruff check src/ tests/  # lint
uv run ruff format .        # format (CI checks --check)
```

- Tests use `asyncio_mode = auto` — no `@pytest.mark.asyncio` needed
- Line length: 120 chars
- No `Co-Authored-By` lines in commits

## Architecture

- **34 MCP tools** across 8 modules: board, project, task, task_workflow, memory, agent, utils, orchestrator
- **6 stores**: TaskStore, ProjectStore, MemoryStore, AgentStore, PlanStore, TraceStore
- All writes use `get_lock()` + `atomic_write()` from `store/locking.py`
- Task files: Markdown + YAML frontmatter in `.agendum/projects/<project>/tasks/`
- Archived tasks: `tasks/done/` subdirectory (auto-archived on completion)
- Execution plans: YAML in `.agendum/projects/<project>/plans/`
- Traces: append-only YAML in `.agendum/traces/<project>/`

## Conventions

- MCP tools: `pm_<module>_<action>` (e.g., `pm_task_create`, `pm_orchestrate_plan`)
- Store methods: lowercase verb (`create_task`, `get_plan`, `write_trace`)
- Tests: `test_<module>.py` or `test_mcp_<module>.py`
- MCP tools return error strings, never raise exceptions

## Key patterns

- **New MCP tool**: add to `tools/<module>.py`, register via closure in `register(mcp, stores, agents)`
- **Orchestrator tools**: add to `tools/orchestrator/<submodule>.py`, reuse helpers from `_helpers.py`
- **Store writes**: always `with get_lock(path): ... atomic_write(path, content)`
- **File moves (archive)**: read → `atomic_write` to dest → `unlink` source → clean up `.lock` sidecar
- **Plans always start DRAFT** — caller approves after human review
- **Traces are append-only** — one file per execution attempt, never modified
- **Dependency resolution**: always include `list_archived_tasks()` when computing `done_ids`

### Model routing

Configure per-project model tier preferences via `pm_orchestrate_policy`. Models are referenced by generic tiers (e.g., `small`, `large`, `fast`) which the parent agent maps to concrete model names in AGENTS.md.

**ProjectPolicy.model_routing fields:**
- `default` — fallback tier for all tasks
- `review` — tier for review stages (when `review_required=True`)
- `by_category` — dict mapping TaskCategory → tier (e.g., `{"code-complex": "large", "docs": "fast"}`)
- `by_type` — dict mapping TaskType → tier (e.g., `{"dev": "small", "planning": "large"}`)
- `by_task` — dict mapping task ID → tier for task-specific overrides

**Resolution hierarchy** (first match wins):
1. `by_task[task.id]` — task-specific override
2. `by_category[task.category]` — complexity-based routing
3. `by_type[task.type]` — domain-based routing
4. `review` — only for review stages (when `is_review=True`)
5. `default` — final fallback
6. `None` — no recommendation

**Tool integration:**

- `pm_orchestrate_policy(project, model_default=..., model_review=..., model_by_category=..., model_by_type=...)` — configure routing. Call with no args to view.
- `pm_orchestrate_next` includes `**Recommended Model:** <tier>` in dispatch output (only if tier is configured).
- `pm_orchestrate_report` includes `Review model: <tier>` when `review_required=True` and review stage begins.
- `pm_agent_suggest(project, task_id)` includes `Recommended model: <tier>` in suggestions.

## File layout

```
src/agendum/
  server.py        — FastMCP wiring, lazy store init
  models.py        — All Pydantic models (Task, ExecutionPlan, ExecutionTrace, etc.)
  task_graph.py    — topological_levels(), resolve_completions(), detect_cycles()
  store/           — File-backed stores with locking
  tools/           — MCP tool modules (board, project, task, memory, agent, utils)
  tools/orchestrator/  — Planning, dispatch, review, policy (7 tools)
templates/         — CLAUDE.md and AGENTS.md templates for projects using agendum
```

## Migration notes

- `pm_spec_update` -> `pm_project_spec_update`
- `pm_plan_update` -> `pm_project_plan_update`
- `Agent.last_heartbeat` -> `Agent.last_seen`
- `Agent.current_task` -> `Agent.last_task`
