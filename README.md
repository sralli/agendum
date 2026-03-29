<!-- mcp-name: io.github.sralli/agendum -->

# agendum

[![PyPI version](https://img.shields.io/pypi/v/agendum.svg)](https://pypi.org/project/agendum/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/sralli/agendum/actions/workflows/ci.yml/badge.svg)](https://github.com/sralli/agendum/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Universal project management for AI coding agents.**

An MCP server that gives any AI agent (Claude Code, Cursor, OpenCode) a shared project management layer — spec-driven planning, task tracking with dependencies, memory, and cross-session continuity. Works for dev, docs, email, and life organization.

## Quick Start

```bash
# 1. Install
pip install agendum
# or: uvx agendum --help

# 2. Add to Claude Code
claude mcp add agendum -- uvx agendum --home serve

# 3. Start managing projects
# (in Claude Code, the pm_* tools are now available)
```

## Installation

### Claude Code

```bash
claude mcp add agendum -- uvx agendum --home serve
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agendum": {
      "command": "uvx",
      "args": ["agendum", "--home", "serve"]
    }
  }
}
```

### Cursor

Add to Cursor Settings > MCP Servers:

```json
{
  "agendum": {
    "command": "uvx",
    "args": ["agendum", "--home", "serve"]
  }
}
```

### CLI (standalone)

```bash
agendum init                                    # Initialize board
agendum project create my-app                   # Create a project
agendum task create my-app "Build auth" -p high # Add tasks
agendum task list my-app                        # View board
agendum next my-app                             # What to work on next?
agendum status                                  # Dashboard overview
```

## Features

### 32 MCP Tools across 7 Modules

| Group | Tools | Purpose |
|-------|-------|---------|
| **Board** | `pm_board_init`, `pm_board_status` | Initialize and overview |
| **Projects** | `pm_project_create`, `pm_project_list`, `pm_project_get`, `pm_spec_update`, `pm_plan_update` | Multi-project management with living specs |
| **Tasks** | `pm_task_create`, `pm_task_list`, `pm_task_get`, `pm_task_claim`, `pm_task_progress`, `pm_task_complete`, `pm_task_block`, `pm_task_handoff`, `pm_task_next` | Full task lifecycle with dependencies |
| **Memory** | `pm_memory_read`, `pm_memory_write`, `pm_memory_append`, `pm_memory_search` | Cross-session knowledge persistence |
| **Agents** | `pm_agent_register`, `pm_agent_heartbeat`, `pm_agent_list`, `pm_agent_suggest` | Multi-agent coordination and routing |
| **Utils** | `pm_check_deps` | Dependency cycle detection |
| **Orchestrator** | `pm_orchestrate_plan`, `pm_orchestrate_next`, `pm_orchestrate_report`, `pm_orchestrate_status`, `pm_orchestrate_approve`, `pm_orchestrate_review`, `pm_orchestrate_policy` | Structured planning, dispatch, review |

### Key Capabilities

- **Spec-driven planning** — living specifications that evolve with the project
- **Task dependencies** — auto-unblocks tasks when their dependencies complete
- **Cross-session continuity** — pick up exactly where you left off
- **Multi-project boards** — manage dev, docs, personal tasks in one place
- **Agent routing** — suggests which model/agent should handle each task type
- **Handoff context** — structured knowledge transfer between agents
- **Memory system** — project learnings, decisions, and patterns persist across sessions
- **Orchestrated execution** — DAG-based parallel dispatch with topological levels
- **Four-status reporting** — done, done_with_concerns, needs_context, blocked
- **Two-stage review** — spec compliance then code quality, configurable per project
- **Execution traces** — append-only records of every task attempt for analysis

## How It Works

All state is stored as human-readable Markdown files with YAML frontmatter:

```
~/.agendum/
├── config.yaml
├── projects/
│   ├── webapp/
│   │   ├── spec.md              # Living specification
│   │   ├── plan.md              # Task decomposition
│   │   ├── policy.yaml          # Orchestration policy (review, approval)
│   │   ├── tasks/
│   │   │   ├── task-001.md      # Markdown + YAML frontmatter
│   │   │   └── task-002.md
│   │   └── plans/
│   │       └── plan-001.yaml    # Execution plans with DAG levels
│   └── personal/
│       └── tasks/...
├── agents/
├── traces/
│   └── webapp/
│       └── task-001-2026-03-29T10-30-00.yaml  # Execution traces
└── memory/
    ├── project.md               # Shared learnings
    ├── decisions.md             # Key decisions + rationale
    └── patterns.md              # Discovered conventions
```

### Task Lifecycle

```
pending --> in_progress --> review --> done
  |            |              |
  v            v              v
cancelled    blocked        blocked
```

Completing a task automatically unblocks its dependents.

### Task File Example

```markdown
---
id: task-001
project: webapp
title: Implement OAuth2 authentication
status: in_progress
priority: high
type: dev
assigned: claude-code
dependsOn: []
blocks: [task-003, task-004]
acceptanceCriteria:
  - Google OAuth redirect works
  - Tokens stored securely
---

## Context
User needs Google sign-in for the webapp.

## Progress
- [2026-03-28T10:05Z] claude-code — Explored existing auth code
- [2026-03-28T14:30Z] claude-code — All tests passing, PR #42 ready

## Handoff
> OAuth works e2e. Reviewer asked for rate limiting — that's remaining work.
```

## Orchestrated Workflow

For complex work, the orchestrator tools manage structured execution across multiple agents:

```
plan → approve → next → dispatch sub-agents → report → review → next → complete
```

**1. Decompose a goal into tasks:**

```python
pm_orchestrate_plan(
    project="webapp",
    goal="Add user authentication",
    tasks_json='[
        {"title": "DB schema for users/sessions", "type": "dev", "priority": "high"},
        {"title": "User model + validation", "type": "dev", "depends_on_indices": [0]},
        {"title": "Auth endpoints (login/signup)", "type": "dev", "depends_on_indices": [1]}
    ]'
)
# → Creates plan-001 with 3 levels (DRAFT status)
```

**2. Approve and start execution:**

```python
pm_orchestrate_approve(project="webapp", plan_id="plan-001")
# → Plan moves to EXECUTING
```

**3. Get next batch of tasks with context packets:**

```python
pm_orchestrate_next(project="webapp", plan_id="plan-001")
# → Returns Level 0 tasks with goal, acceptance criteria, key files
```

**4. Report completion with four-status system:**

```python
pm_orchestrate_report(project="webapp", task_id="task-001", status="done")
# → Writes execution trace, unblocks Level 1 tasks
```

**5. Review (if policy requires):**

```python
pm_orchestrate_review(project="webapp", task_id="task-001", stage="spec", passed=True)
pm_orchestrate_review(project="webapp", task_id="task-001", stage="quality", passed=True)
# → Task marked DONE, dependents unblocked
```

The orchestrator is runtime-agnostic — it produces structured context packets that any AI agent (Claude Code, Cursor, etc.) uses to dispatch sub-agents via its own runtime.

## Architecture

```
src/agendum/
├── server.py             # MCP server wiring (FastMCP)
├── config.py             # Shared configuration
├── models.py             # Pydantic models
├── task_graph.py         # Dependency resolution + topological levels
├── cli.py                # Click CLI
├── store/
│   ├── __init__.py       # sanitize_name() security utility
│   ├── locking.py        # get_lock() + atomic_write() concurrency primitives
│   ├── task_store.py     # Task Markdown + YAML file I/O
│   ├── project_store.py  # Project specs, plans, and policies
│   ├── memory_store.py   # Scoped memory storage
│   ├── agent_store.py    # Agent persistence across sessions
│   ├── plan_store.py     # Execution plan CRUD
│   └── trace_store.py    # Append-only execution traces
└── tools/                # MCP tool modules
    ├── board.py          # 2 tools
    ├── project.py        # 5 tools
    ├── task.py           # 10 tools
    ├── memory.py         # 4 tools
    ├── agent.py          # 4 tools
    ├── utils.py          # 1 tool (pm_check_deps)
    └── orchestrator/     # 7 tools
        ├── __init__.py   # Register all orchestrator submodules
        ├── _helpers.py   # Shared helpers (resolve_and_unblock, parse_csv)
        ├── planning.py   # pm_orchestrate_plan, pm_orchestrate_status
        ├── dispatch.py   # pm_orchestrate_next, pm_orchestrate_report
        ├── review.py     # pm_orchestrate_review, pm_orchestrate_approve
        └── policy.py     # pm_orchestrate_policy
```

## Development

```bash
git clone https://github.com/sralli/agendum.git
cd agendum
uv sync
uv run pytest tests/ -v     # 196 tests
uv run ruff check .          # Lint
uv run ruff format --check . # Format check
```

## License

MIT
