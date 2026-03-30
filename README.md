<!-- mcp-name: io.github.sralli/agendum -->

# agendum

[![PyPI version](https://img.shields.io/pypi/v/agendum.svg)](https://pypi.org/project/agendum/)
[![Downloads](https://img.shields.io/pypi/dm/agendum.svg)](https://pypi.org/project/agendum/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/sralli/agendum/actions/workflows/ci.yml/badge.svg)](https://github.com/sralli/agendum/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Universal project management for AI coding agents.**

An [MCP server](https://modelcontextprotocol.io/) that gives any AI agent (Claude Code, Cursor, Windsurf, Cline, OpenCode) a shared project management layer — spec-driven planning, task tracking with dependencies, memory, and cross-session continuity.

## Why agendum?

AI coding agents are powerful but stateless. They forget what they did last session, can't coordinate with other agents, and have no structured way to break down complex work. agendum fixes this:

- **Memory across sessions** — An agent picks up exactly where the last one left off. Decisions, gotchas, and progress persist in git-friendly Markdown files.
- **Multi-agent coordination** — Multiple agents (Claude Code on your laptop, Cursor on your desktop, a CI agent) share the same task board. Structured handoffs prevent duplicate work.
- **Orchestrated execution** — Break a goal into a dependency DAG, dispatch tasks to sub-agents with rich context packets (project rules, memory, prior handoffs), and track completion with four-status reporting.
- **Works with any MCP client** — Not locked to one IDE or agent. Any tool that speaks MCP can use agendum's 32 tools.
- **Git-native** — All state is human-readable Markdown + YAML in a `.agendum/` directory. Diff it, commit it, review it in PRs.
- **Beyond code** — Track dev tasks, docs, emails, personal todos, research — anything an agent (or human) needs to manage.

### Example: What It Looks Like in Claude Code

```
You: Create a project for our API rewrite and break it into tasks

Agent: I'll set up the project board.
  → pm_board_init()
  → pm_project_create(name="api-rewrite", description="Migrate REST API to GraphQL")
  → pm_task_create(project="api-rewrite", title="Schema design", priority="high")
  → pm_task_create(project="api-rewrite", title="Resolver layer", depends_on=["task-001"])
  → pm_task_create(project="api-rewrite", title="Auth middleware", depends_on=["task-001"])
  → pm_task_create(project="api-rewrite", title="Integration tests", depends_on=["task-002","task-003"])

Created project "api-rewrite" with 4 tasks:
  Level 0: task-001 (Schema design)
  Level 1: task-002 (Resolver layer) + task-003 (Auth middleware)  ← parallel
  Level 2: task-004 (Integration tests)

You: What should I work on?

Agent:
  → pm_task_next(project="api-rewrite")

  Suggested: task-001 "Schema design" [high priority, no dependencies]

You: Done with the schema. Here's what I decided...

Agent:
  → pm_task_handoff(project="api-rewrite", task_id="task-001",
      completed=["GraphQL schema defined", "Types for User, Product, Order"],
      decisions=["Using code-first with Strawberry"],
      gotchas=["N+1 queries need DataLoader"])
  → pm_task_complete(project="api-rewrite", task_id="task-001")

  Completed task-001. Unblocked: task-002, task-003
  Next session or agent will see your decisions and gotchas.
```

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
| **Projects** | `pm_project_create`, `pm_project_list`, `pm_project_get`, `pm_project_spec_update`, `pm_project_plan_update` | Multi-project management with living specs |
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
