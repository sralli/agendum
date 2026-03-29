# agendum

Universal project management for AI coding agents. Python 3.13+, uv, FastMCP.

## Quick reference

```bash
uv run pytest               # 196 tests, all must pass
uv run ruff check src/ tests/  # lint
uv run ruff format .        # format (CI checks --check)
```

- Tests use `asyncio_mode = auto` — no `@pytest.mark.asyncio` needed
- Line length: 120 chars
- No `Co-Authored-By` lines in commits

## Architecture

- **32 MCP tools** across 7 modules: board, project, task, memory, agent, utils, orchestrator
- **6 stores**: TaskStore, ProjectStore, MemoryStore, AgentStore, PlanStore, TraceStore
- All writes use `get_lock()` + `atomic_write()` from `store/locking.py`
- Task files: Markdown + YAML frontmatter in `.agendum/projects/<project>/tasks/`
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
- **Plans always start DRAFT** — caller approves after human review
- **Traces are append-only** — one file per execution attempt, never modified

## File layout

```
src/agendum/
  server.py        — FastMCP wiring, lazy store init
  models.py        — All Pydantic models (Task, ExecutionPlan, ExecutionTrace, etc.)
  task_graph.py    — topological_levels(), resolve_completions(), detect_cycles()
  store/           — File-backed stores with locking
  tools/           — MCP tool modules (board, project, task, memory, agent, utils)
  tools/orchestrator/  — Planning, dispatch, review, policy (7 tools)
```
