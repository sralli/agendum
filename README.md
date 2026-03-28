# agentpm

Universal project management for AI coding agents.

An MCP server + CLI that gives any AI agent (Claude Code, Cursor, OpenCode) a shared project management layer with spec-driven planning, task tracking, dependency resolution, memory, and cross-session continuity.

## Quick Start

```bash
# Install
uv tool install agentpm

# Add to Claude Code
claude mcp add agentpm -- uv run --project /path/to/agentpm agentpm serve

# Or use the CLI directly
agentpm init                          # Initialize .agentpm/ in current repo
agentpm project create my-app         # Create a project
agentpm task create my-app "Build auth" -p high  # Add tasks
agentpm task list my-app              # View board
agentpm next my-app                   # What should I work on?
agentpm serve                         # Start MCP server
```

## MCP Tools (24 tools)

### Board & Projects
- `pm_board_init` / `pm_board_status`
- `pm_project_create` / `pm_project_list` / `pm_project_get`
- `pm_spec_update` / `pm_plan_update`

### Tasks
- `pm_task_create` / `pm_task_list` / `pm_task_get`
- `pm_task_claim` / `pm_task_update` / `pm_task_complete`
- `pm_task_block` / `pm_task_handoff` / `pm_task_next`

### Memory
- `pm_memory_read` / `pm_memory_write` / `pm_memory_append` / `pm_memory_search`

### Agents
- `pm_agent_register` / `pm_agent_heartbeat` / `pm_agent_list`

### Utilities
- `pm_check_deps` (dependency cycle detection)

## Storage

All state lives as git-native Markdown files in `.agentpm/`:

```
.agentpm/
├── config.yaml
├── projects/
│   └── my-app/
│       ├── spec.md          # Living specification
│       ├── plan.md          # Task decomposition plan
│       └── tasks/
│           ├── task-001.md  # Markdown + YAML frontmatter
│           └── task-002.md
├── agents/
└── memory/
    ├── project.md
    ├── decisions.md
    └── patterns.md
```

Tasks are human-readable Markdown with YAML frontmatter — readable by any text editor, diffable by git.

## Architecture

- **MCP Server** (FastMCP) — any MCP-capable agent connects instantly
- **Git-native storage** — zero infrastructure, works offline
- **Dependency engine** — auto-unblocks tasks, cycle detection, smart next-task suggestion
- **Memory system** — project, decisions, patterns scopes
- **Agent registry** — track who's working on what

## Development

```bash
git clone https://github.com/yourusername/agentpm
cd agentpm
uv sync
uv run pytest tests/ -v
```

## License

MIT
