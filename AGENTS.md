# agendum — Agent Development Guide

> Read this before making any changes to the codebase.

## Orchestrated workflow

This project uses its own agendum MCP tools. All non-trivial work follows this pipeline.

### Pipeline

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

1. **Orient**: `pm_board_status` → `pm_task_list project=agendum` → `pm_memory_search`
2. **Plan**: harness plan mode → `pm_orchestrate_plan` → `pm_orchestrate_approve`
3. **Dispatch**: `pm_orchestrate_next` → spawn subagent with context packet
4. **Report**: subagent calls `pm_orchestrate_report` with status
5. **Review** (only if report returns "awaiting review"): `pm_orchestrate_review stage=spec` then `stage=quality`
6. If review fails → subagent fixes → re-report → re-review
7. If report says "done" with no review notice → task is complete, proceed to next
8. **Repeat** until plan complete → `pm_orchestrate_status` → test → commit

### Skip orchestration for

- Single-line fixes (typos, version bumps)
- Pure research/exploration
- README-only changes

### Subagent contract

- Receives context packet from `pm_orchestrate_next`
- MUST call `pm_orchestrate_report` when done
- MUST NOT modify files outside task scope
- MUST run relevant tests before reporting `done`
- Use `pm_task_progress` for intermediate updates

## Quick start

```bash
uv sync                          # install dependencies
uv run pytest tests/ -v          # run all tests
uv run ruff check .              # lint
```

## Project structure

```
src/agendum/
  server.py          — FastMCP server; wires _Stores and registers all tool modules
  cli.py             — CLI entry point
  config.py          — resolve_root(): locates .agendum/ directory
  models.py          — Pydantic models: Task, Project, Agent, AgentHandoffRecord, etc.
  task_graph.py      — resolve_completions(), suggest_next_task() — dependency logic
  env_context.py     — get_device_name(), get_git_branch(), get_working_dir()

  store/
    locking.py       — get_lock(path), atomic_write(path, content) — concurrency primitives
    task_store.py    — TaskStore: CRUD + archive for task Markdown files
    project_store.py — ProjectStore: project init, list, get, policies
    memory_store.py  — MemoryStore: append/read/search persistent agent notes
    agent_store.py   — AgentStore: agent registration and heartbeat persistence
    plan_store.py    — PlanStore: execution plan CRUD (YAML files)
    trace_store.py   — TraceStore: append-only execution traces

  tools/
    board.py         — pm_board_init, pm_board_status
    project.py       — pm_project_create, pm_project_list, pm_project_get
    task.py          — pm_task_{create,list,get,archive,archive_all}
    task_workflow.py  — pm_task_{claim,progress,complete,block,handoff,next}
    memory.py        — pm_memory_{write,append,read,search}
    agent.py         — pm_agent_{register,heartbeat,list,suggest}
    utils.py         — pm_check_deps
    project.py       — pm_project_{create,list,get,spec_update,plan_update}
    orchestrator/    — Structured planning, dispatch, review, and policy
      __init__.py    — register() delegates to submodules
      _helpers.py    — resolve_and_unblock(), check_plan_level_complete(), parse_csv()
      planning.py    — pm_orchestrate_plan, pm_orchestrate_status
      dispatch.py    — pm_orchestrate_next, pm_orchestrate_report
      review.py      — pm_orchestrate_review, pm_orchestrate_approve
      policy.py      — pm_orchestrate_policy
      enrichment.py  — ContextEnricher pipeline
      sources.py     — ProjectRules, Memory, Handoff, ReviewHistory, ExternalReferences

tests/
  conftest.py        — mcp_server fixture, call() helper
  test_mcp_*.py      — integration tests per tool module
  test_*_store.py    — unit tests for store classes
  test_concurrent.py — locking/race-condition tests
  test_security.py   — path traversal and input sanitization tests

templates/
  CLAUDE.md          — Template for projects adopting agendum
  AGENTS.md          — Template agent guide for projects adopting agendum
```

## Three-tier boundaries

### Always
- Use `get_lock(path)` context manager for every store write
- Run `uv run pytest tests/ -v` before submitting changes
- Add type annotations to all new public functions
- Follow the `register(mcp, stores, agents)` pattern for new tool modules
- Keep MCP tool return values as plain strings (not raised exceptions)
- Include `list_archived_tasks()` when computing `done_ids` for dependency resolution

### Ask first
- Changing the Markdown/YAML format of task files — breaks existing boards
- Modifying `models.py` Task/Project fields — breaks serialization of on-disk data
- Touching `locking.py` or `atomic_write()` — concurrency-critical
- Adding new dependencies to `pyproject.toml`
- Changing MCP tool names — breaks client configurations

### Never
- `path.write_text()` or `open(path, "w")` without `get_lock()` — race condition
- `shutil.move()` for file moves — use read → `atomic_write` → `unlink` instead
- Raise exceptions from MCP tool functions — return error strings instead
- Modify files under `.agendum/` — that is runtime board data, not source
- Skip the test suite — all tests must pass before any PR
- Add `Co-Authored-By` lines to commits

---

## Adding a new MCP tool

All tool modules export a single `register(mcp, stores, agents)` function. Tools are
decorated with `@mcp.tool()` and defined as closures that capture `stores` and `agents`.

```python
def register(mcp, stores, agents):
    @mcp.tool()
    def pm_task_create(project: str, title: str, priority: str = "medium") -> str:
        """Create a new task in a project."""
        try:
            task = stores.task.create_task(project=project, title=title, priority=priority)
        except ValueError as e:
            return f"Error: {e}"
        return f"Created task {task.id}: {task.title}"
```

Wire in `src/agendum/server.py` and `tests/conftest.py`.

---

## Store write pattern

Every write must go through `get_lock()` + `atomic_write()`:

```python
def update_task(self, project, task_id, **updates):
    path = _task_path(self.root, project, task_id)
    with get_lock(path):
        task = self.get_task(project, task_id)
        if not task:
            return None
        for key, value in updates.items():
            if key in _MUTABLE_FIELDS:
                setattr(task, key, value)
        task.updated = datetime.now(UTC)
        atomic_write(path, task_to_markdown(task))
    return task
```

For file moves (archive): read content → `atomic_write` to destination → `unlink` source → clean up `.lock` sidecar.

---

## Test conventions

- `asyncio_mode = auto` — no `@pytest.mark.asyncio` needed
- MCP tools return `str` — assert on string content, not exceptions
- Use `pytest.raises` for store-level exception tests
- `mcp_server` fixture returns `(mcp, stores, agents_registry)` 3-tuple

---

## Naming conventions

| Category | Pattern | Examples |
|---|---|---|
| MCP tools | `pm_{noun}_{verb}` | `pm_task_create`, `pm_board_status` |
| Store methods | `snake_case` verbs | `update_task()`, `archive_task()` |
| Test functions | `test_{tool_name}_{scenario}` | `test_task_create_happy` |
| Models | `PascalCase` Pydantic | `Task`, `ExecutionPlan` |

---

## Orchestrator conventions

- Plans always start as DRAFT → approved via `pm_orchestrate_approve`
- Traces are append-only — one file per execution attempt
- Context packets built at plan creation, served by `pm_orchestrate_next`
- Four-status reporting: `done`, `done_with_concerns`, `needs_context`, `blocked`
- Review is two-stage: spec (acceptance criteria) then quality (code quality)
- Review is opt-in via `ProjectPolicy.review_required`

---

## Sources

- MCP Python SDK: https://py.sdk.modelcontextprotocol.io/
- Ruff rules: https://docs.astral.sh/ruff/rules/
