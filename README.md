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

### 25 MCP Tools

| Group | Tools | Purpose |
|-------|-------|---------|
| **Board** | `pm_board_init`, `pm_board_status` | Initialize and overview |
| **Projects** | `pm_project_create`, `pm_project_list`, `pm_project_get`, `pm_spec_update`, `pm_plan_update` | Multi-project management with living specs |
| **Tasks** | `pm_task_create`, `pm_task_list`, `pm_task_get`, `pm_task_claim`, `pm_task_progress`, `pm_task_complete`, `pm_task_block`, `pm_task_handoff`, `pm_task_next` | Full task lifecycle with dependencies |
| **Memory** | `pm_memory_read`, `pm_memory_write`, `pm_memory_append`, `pm_memory_search` | Cross-session knowledge persistence |
| **Agents** | `pm_agent_register`, `pm_agent_heartbeat`, `pm_agent_list`, `pm_agent_suggest` | Multi-agent coordination and routing |
| **Utils** | `pm_check_deps` | Dependency cycle detection |

### Key Capabilities

- **Spec-driven planning** — living specifications that evolve with the project
- **Task dependencies** — auto-unblocks tasks when their dependencies complete
- **Cross-session continuity** — pick up exactly where you left off
- **Multi-project boards** — manage dev, docs, personal tasks in one place
- **Agent routing** — suggests which model/agent should handle each task type
- **Handoff context** — structured knowledge transfer between agents
- **Memory system** — project learnings, decisions, and patterns persist across sessions

## How It Works

All state is stored as human-readable Markdown files with YAML frontmatter:

```
~/.agendum/
├── config.yaml
├── projects/
│   ├── webapp/
│   │   ├── spec.md              # Living specification
│   │   ├── plan.md              # Task decomposition
│   │   └── tasks/
│   │       ├── task-001.md      # Markdown + YAML frontmatter
│   │       └── task-002.md
│   └── personal/
│       └── tasks/...
├── agents/
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

## Architecture

```
src/agendum/
├── server.py           # MCP server wiring (FastMCP)
├── config.py           # Shared configuration
├── models.py           # Pydantic models
├── task_graph.py       # Dependency resolution engine
├── cli.py              # Click CLI
├── store/
│   ├── __init__.py     # sanitize_name() security utility
│   ├── task_store.py   # Markdown + YAML file I/O
│   ├── memory_store.py # Scoped memory storage
│   └── project_store.py
└── tools/              # MCP tool modules
    ├── board.py        # 2 tools
    ├── project.py      # 5 tools
    ├── task.py         # 10 tools
    ├── memory.py       # 4 tools
    ├── agent.py        # 4 tools
    └── utils.py        # 1 tool
```

## Development

```bash
git clone https://github.com/sralli/agendum.git
cd agendum
uv sync
uv run pytest tests/ -v     # 57 tests
uv run ruff check .          # Lint
uv run ruff format --check . # Format check
```

## License

MIT
