# agendum — Agent Development Guide

> Read this before making any changes to the codebase.

## Quick Start

```bash
uv sync                          # install dependencies
uv run pytest tests/ -v          # run all 135+ tests
uv run ruff check .              # lint
uv run mypy src/agendum          # type-check
```

## Project Structure

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
    task_store.py    — TaskStore: CRUD for task Markdown files with YAML frontmatter
    project_store.py — ProjectStore: project init, list, get
    memory_store.py  — MemoryStore: append/read/search persistent agent notes
    agent_store.py   — AgentStore: agent registration and heartbeat persistence

  tools/
    board.py         — pm_board_init, pm_board_status
    project.py       — pm_project_create, pm_project_list, pm_project_get
    task.py          — pm_task_{create,list,get,claim,progress,complete,block,handoff,next}
    memory.py        — pm_memory_{write,append,read,search}
    agent.py         — pm_agent_{register,heartbeat,list,suggest}
    utils.py         — pm_check_deps, pm_plan_update, pm_spec_update

tests/
  conftest.py        — mcp_server fixture, call() helper
  test_mcp_*.py      — integration tests per tool module
  test_*_store.py    — unit tests for store classes
  test_concurrent.py — locking/race-condition tests
  test_security.py   — path traversal and input sanitization tests
```

## Three-Tier Boundaries

### Always
- Use `get_lock(path)` context manager for every store write
- Run `uv run pytest tests/ -v` before submitting changes
- Add type annotations to all new public functions
- Follow the `register(mcp, stores, agents)` pattern for new tool modules
- Keep MCP tool return values as plain strings (not raised exceptions)

### Ask first
- Changing the Markdown/YAML format of task files — breaks existing boards
- Modifying `models.py` Task/Project fields — breaks serialization of on-disk data
- Touching `locking.py` or `atomic_write()` — concurrency-critical
- Adding new dependencies to `pyproject.toml`
- Changing MCP tool names — breaks client configurations

### Never
- `path.write_text()` or `open(path, "w")` without `get_lock()` — race condition
- Raise exceptions from MCP tool functions — return error strings instead (e.g. `return f"Error: {e}"`)
- Modify files under `.agendum/` — that is runtime board data, not source
- Skip the test suite — all 135+ tests must pass before any PR

---

## Adding a New MCP Tool

All tool modules export a single `register(mcp, stores, agents)` function. Tools are
decorated with `@mcp.tool()` and defined as closures that capture `stores` and `agents`.

Real pattern from `src/agendum/tools/task.py`:

```python
def register(mcp, stores, agents):
    """Register task tools on the MCP server."""

    @mcp.tool()
    def pm_task_create(
        project: str,
        title: str,
        description: str = "",
        priority: str = "medium",
    ) -> str:
        """Create a new task in a project."""
        try:
            task = stores.task.create_task(
                project=project,
                title=title,
                context=description,
                priority=priority,
            )
        except ValueError as e:
            return f"Error: {e}"
        return f"Created task {task.id}: {task.title}"
```

Simpler example from `src/agendum/tools/board.py`:

```python
def register(mcp, stores, agents):
    """Register board tools on the MCP server."""

    @mcp.tool()
    def pm_board_init(name: str = "agendum") -> str:
        """Initialize .agendum/ directory in the current project."""
        config = stores.project.init_board(name)
        return f"Initialized agendum board at {stores.root}. Config: {json.dumps(config.model_dump())}"
```

Wire the new module in `src/agendum/server.py` (and in `tests/conftest.py`):

```python
from agendum.tools import mymodule
mymodule.register(mcp, stores, agents_registry)
```

---

## Store Write Pattern

Every write to a task file must go through `get_lock()` + `atomic_write()`.
Real example from `src/agendum/store/task_store.py`:

```python
def update_task(self, project: str, task_id: str, **updates) -> Task | None:
    """Update whitelisted fields and write back to disk (locked + atomic)."""
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

def add_progress(self, project: str, task_id: str, agent: str, message: str) -> Task | None:
    """Append a progress entry (locked + atomic to prevent concurrent data loss)."""
    path = _task_path(self.root, project, task_id)
    with get_lock(path):
        task = self.get_task(project, task_id)
        if not task:
            return None
        task.progress.append(
            ProgressEntry(timestamp=datetime.now(UTC), agent=agent, message=message)
        )
        task.updated = datetime.now(UTC)
        atomic_write(path, task_to_markdown(task))
    return task
```

`get_lock(path)` creates a `.lock` sidecar file next to the target.
`atomic_write(path, content)` writes to a `.tmp` file then calls `os.replace()` (POSIX-atomic).

---

## Test Conventions

The `mcp_server` fixture in `tests/conftest.py` returns `(mcp, stores, agents_registry)`:

```python
@pytest_asyncio.fixture
async def mcp_server(tmp_path: Path):
    """Fresh FastMCP instance with isolated stores, wired for all tool modules."""
    root = tmp_path / ".agendum"
    root.mkdir()

    stores = _Stores()
    stores._root = root  # bypass resolve_root()

    agents_registry: dict = {}

    mcp = FastMCP("agendum-test")
    board.register(mcp, stores, agents_registry)
    project.register(mcp, stores, agents_registry)
    task.register(mcp, stores, agents_registry)
    memory.register(mcp, stores, agents_registry)
    agent.register(mcp, stores, agents_registry)
    utils.register(mcp, stores, agents_registry)

    return mcp, stores, agents_registry


async def call(mcp: FastMCP, tool_name: str, **kwargs) -> str:
    """Call an MCP tool and return the text result."""
    content, _ = await mcp.call_tool(tool_name, kwargs)
    return content[0].text
```

Typical test shape:

```python
async def test_task_create_happy(mcp_server):
    mcp, stores, agents = mcp_server
    await call(mcp, "pm_board_init", name="test")
    await call(mcp, "pm_project_create", name="myproject")
    result = await call(mcp, "pm_task_create", project="myproject", title="Do a thing")
    assert "task-001" in result
```

Key notes:
- `asyncio_mode = auto` is set in `pyproject.toml` — do **not** add `@pytest.mark.asyncio`
- All MCP tools return `str` — error paths assert `"error" in result.lower()` rather than catching exceptions
- `tmp_path` is provided by pytest but is not passed to `mcp_server` directly — `stores._root` is what controls isolation

---

## Naming Conventions

| Category | Pattern | Examples |
|---|---|---|
| MCP tools | `pm_{noun}_{verb}` | `pm_task_create`, `pm_board_status` |
| Store methods | `snake_case` verbs | `update_task()`, `add_progress()` |
| Test functions | `test_{tool_name}_{scenario}` | `test_task_create_happy`, `test_task_block_missing` |
| Models | `PascalCase` Pydantic `BaseModel` | `Task`, `Project`, `AgentHandoffRecord` |
| Tool modules | `snake_case` noun | `task.py`, `board.py`, `memory.py` |

---

## Common Pitfalls

1. **Tools must return strings, not raise.** Every tool catches `ValueError` and returns `f"Error: {e}"`. Unhandled exceptions crash the MCP transport. Always wrap store calls in `try/except`.

2. **No `@pytest.mark.asyncio` needed.** The project uses `asyncio_mode = auto` in `pyproject.toml`. Adding the decorator is harmless but unnecessary; omitting it is correct.

3. **`tmp_path` is not used directly in `mcp_server` tests.** The fixture creates its own `root = tmp_path / ".agendum"` and assigns it to `stores._root`. Don't pass `tmp_path` as an argument to tool calls.

4. **`mcp_server` returns a 3-tuple.** Unpack as `mcp, stores, agents = mcp_server`. Forgetting `agents` will cause an unpack error.

5. **Task IDs are sequential per project.** IDs are generated as `task-001`, `task-002`, etc. based on the highest existing number in the project's tasks directory. Never hard-code an ID without first checking the project state.

---

## Sources

- MCP Python SDK: https://py.sdk.modelcontextprotocol.io/
- JetBrains AI coding guidelines: https://blog.jetbrains.com/idea/2025/05/coding-guidelines-for-your-ai-agents/
- Addy Osmani spec structure: https://addyosmani.com/blog/good-spec/
- Ruff rules: https://docs.astral.sh/ruff/rules/
