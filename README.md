<!-- mcp-name: io.github.sralli/agendum -->

# agendum

[![PyPI version](https://img.shields.io/pypi/v/agendum.svg)](https://pypi.org/project/agendum/)
[![Downloads](https://img.shields.io/pypi/dm/agendum.svg)](https://pypi.org/project/agendum/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/sralli/agendum/actions/workflows/ci.yml/badge.svg)](https://github.com/sralli/agendum/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Project memory and scoping engine for AI coding agents.**

An [MCP server](https://modelcontextprotocol.io/) that gives any AI agent (Claude Code, Cursor, Windsurf, Cline, OpenCode) persistent project state, scoped work packages, and cross-session continuity.

## Why agendum?

AI coding agents are powerful but stateless. They forget what they did last session, lose context between tasks, and have no structured way to scope complex work. agendum fixes this:

- **Session continuity** — An agent picks up exactly where the last one left off. Decisions, progress, and context persist in git-friendly Markdown files.
- **Scoped work packages** — `pm_next` returns a bounded work package with enriched context (project rules, memory, dependency info), so the agent knows exactly what to do and what NOT to touch.
- **Cross-project learning** — Patterns and decisions learned in one project inform work in others via global learnings.
- **Works with any MCP client** — Not locked to one IDE or agent. Any tool that speaks MCP can use agendum's 11 tools.
- **Git-native** — All state is human-readable Markdown + YAML in a `.agendum/` directory. Diff it, commit it, review it in PRs.

### Example: What It Looks Like in Claude Code

```
You: I have a plan file for the API rewrite. Ingest it.

Agent:
  → pm_ingest(project="api-rewrite", plan_path="plan.md")

  Ingested 4 board items from plan:
    item-001: Schema design [high]
    item-002: Resolver layer (depends on item-001)
    item-003: Auth middleware (depends on item-001)
    item-004: Integration tests (depends on item-002, item-003)

You: What should I work on?

Agent:
  → pm_next(project="api-rewrite")

  Work package for item-001 "Schema design":
    Context: project rules, memory from last session
    Scope: Define GraphQL schema types
    Acceptance criteria: Types for User, Product, Order

You: Done with the schema. Here's what I decided...

Agent:
  → pm_done(project="api-rewrite", item_id="item-001",
      decisions=["Using code-first with Strawberry"],
      patterns=["N+1 queries need DataLoader"])

  Completed item-001. Unblocked: item-002, item-003
  Next session: pm_status → pm_next → continue
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

### Cursor

Add to `.cursor/mcp.json` in your project root:

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

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

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

### VS Code (GitHub Copilot)

Add to `.vscode/mcp.json` in your project root:

```json
{
  "servers": {
    "agendum": {
      "command": "uvx",
      "args": ["agendum", "--home", "serve"]
    }
  }
}
```

### Cline

Add to your Cline MCP settings (Settings > MCP Servers > Edit):

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

### Roo Code

Add to your Roo Code MCP settings:

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

### CLI (standalone)

```bash
pip install agendum
# or: uvx agendum --help

agendum init                                    # Initialize board
agendum project create my-app                   # Create a project
agendum status                                  # Dashboard overview
```

## Features

### 11 MCP Tools

| Tool | Purpose |
|------|---------|
| `pm_init` | Initialize agendum board directory (optional — auto-initializes on first use) |
| `pm_project` | Create, list, or get projects |
| `pm_status` | Board overview — item counts, recent progress, suggested next task |
| `pm_add` | Add a board item to a project |
| `pm_board` | View and filter the project board |
| `pm_ingest` | Import a plan file into bounded board items with dependencies |
| `pm_next` | Get next scoped work package with enriched context |
| `pm_done` | Complete an item, record decisions and patterns |
| `pm_block` | Report a task as blocked with reason |
| `pm_memory` | Read, write, append, or search project memory |
| `pm_learn` | Record cross-project or project-scoped learnings |

### Key Capabilities

- **Plan ingestion** — `pm_ingest` reads a plan file and creates bounded board items with dependencies
- **Scoped work packages** — `pm_next` returns enriched context (project rules, memory, dependency info)
- **Cross-session continuity** — pick up exactly where you left off
- **Decision tracking** — `pm_done` captures decisions and patterns for future sessions
- **Cross-project learnings** — patterns discovered in one project inform others
- **Dependency resolution** — topological ordering, auto-unblocking when dependencies complete
- **Enrichment pipeline** — pluggable context sources (project rules, memory, dependencies)
- **Git-native** — all state is Markdown + YAML, diffable and committable

## How It Works

All state is stored as human-readable Markdown files with YAML frontmatter:

```
~/.agendum/
├── config.yaml
├── projects/
│   ├── webapp/
│   │   ├── project.yaml         # Project metadata
│   │   ├── board/
│   │   │   ├── item-001.md      # Markdown + YAML frontmatter
│   │   │   └── item-002.md
│   │   └── learnings/           # Project-scoped learnings
│   │       └── learning-001.md
│   └── personal/
│       └── board/...
├── learnings/                   # Cross-project learnings
│   └── learnings.md
└── memory/
    ├── project.md               # Shared learnings
    ├── decisions.md             # Key decisions + rationale
    └── patterns.md              # Discovered conventions
```

### The Flow

```
1. PLAN (harness)    brainstorming → writing-plans → plan file
2. INGEST (agendum)  pm_ingest reads plan → creates bounded board items
3. SCOPE (agendum)   pm_next returns scoped work package with context
4. EXECUTE (harness)  Agent works within the scoped package
5. REPORT (agendum)  pm_done records completion, decisions, patterns
6. RESUME (agendum)  Next session: pm_status → pm_next → continue
```

## Architecture

```
src/agendum/
├── server.py             # MCP server wiring (FastMCP)
├── config.py             # Shared configuration
├── models.py             # Pydantic models (BoardItem, WorkPackage)
├── tools.py              # 11 MCP tools
├── task_graph.py          # Dependency resolution + topological levels
├── cli.py                # CLI interface
├── enrichment/
│   ├── pipeline.py       # ContextEnricher, ContextSource protocol
│   └── sources.py        # ProjectRulesSource, MemorySource, DependencySource
└── store/
    ├── locking.py        # get_lock() + atomic_write() concurrency primitives
    ├── board_store.py    # BoardItem CRUD
    ├── board_format.py   # Markdown ↔ BoardItem serialization
    ├── project_store.py  # Project metadata
    ├── memory_store.py   # Scoped memory storage
    └── learnings_store.py # Global cross-project learnings
```

## Development

```bash
git clone https://github.com/sralli/agendum.git
cd agendum
uv sync
uv run pytest tests/ -v     # all tests
uv run ruff check .          # lint
uv run ruff format --check . # format check
```

## License

MIT
