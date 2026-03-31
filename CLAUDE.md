# agendum

Project memory and scoping engine for AI coding agents. Python 3.13+, uv, FastMCP.

## Workflow

agendum augments the harness (Claude Code + superpowers + plan mode). It does NOT compete with it.

### Separation of concerns

| Concern | Owner |
|---------|-------|
| Brainstorming & design | Superpowers (brainstorming skill) |
| Planning & task breakdown | Superpowers (writing-plans) + plan mode |
| Subagent dispatch | Claude Code Agent tool |
| **Persistent project state** | **agendum** |
| **Bounded work packages** | **agendum** |
| **Cross-session memory** | **agendum** |
| **Project board / backlog** | **agendum** |

### The flow

```
1. PLAN (harness)    brainstorming → writing-plans → plan file
2. INGEST (agendum)  pm_ingest reads plan → creates bounded board items
3. SCOPE (agendum)   pm_next returns scoped work package with context
4. EXECUTE (harness)  Agent works within the scoped package
5. REPORT (agendum)  pm_done records completion, decisions, patterns
6. RESUME (agendum)  Next session: pm_status → pm_next → continue
```

### When to skip agendum

- Single-line fixes (typos, version bumps)
- Pure research/exploration (no code changes)

## Quick reference

```bash
uv run pytest               # all tests must pass
uv run ruff check src/ tests/  # lint
uv run ruff format .        # format
```

## Architecture

- **11 MCP tools** in `tools.py`
- **4 stores**: BoardStore, ProjectStore, MemoryStore, LearningsStore
- **Enrichment pipeline**: `enrichment/pipeline.py` + `enrichment/sources.py`
- All writes use `get_lock()` + `atomic_write()` from `store/locking.py`
- Board items: Markdown + YAML frontmatter in `.agendum/projects/<project>/board/`
- Global learnings: `.agendum/learnings/`
- Memory: `.agendum/memory/`

## Conventions

- MCP tools: `pm_<name>` (e.g., `pm_add`, `pm_next`, `pm_done`)
- Store methods: lowercase verb (`create_item`, `get_item`, `list_items`)
- Tests: `test_<module>.py`
- MCP tools return error strings, never raise exceptions
- No Co-Authored-By lines in commits
- Line length: 120 chars

## File layout

```
src/agendum/
  server.py         — FastMCP wiring, lazy store init
  models.py         — Pydantic models (BoardItem, WorkPackage)
  tools.py          — 11 MCP tools
  config.py         — resolve_root()
  cli.py            — CLI interface
  task_graph.py     — Dependency resolution (topological levels, cycle detection)
  enrichment/       — Context enrichment pipeline
    pipeline.py     — ContextEnricher, ContextSource protocol
    sources.py      — ProjectRulesSource, MemorySource, DependencySource
  store/            — File-backed stores with locking
    locking.py      — atomic_write, get_lock, next_sequential_id
    board_store.py  — BoardItem CRUD
    board_format.py — Markdown ↔ BoardItem serialization
    project_store.py — Project metadata
    memory_store.py — Scoped memory (project, decisions, patterns, learnings)
    learnings_store.py — Global cross-project learnings
```
