"""agentpm MCP server — wires up stores and registers tool modules."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agentpm.config import resolve_root
from agentpm.models import Agent
from agentpm.store.agent_store import AgentStore
from agentpm.store.memory_store import MemoryStore
from agentpm.store.project_store import ProjectStore
from agentpm.store.task_store import TaskStore
from agentpm.tools import agent, board, memory, project, task, utils

# --- Lazy store initialization ---


class _Stores:
    """Lazy-initialized stores. Resolves root at first access, not import time."""

    def __init__(self):
        self._task: TaskStore | None = None
        self._project: ProjectStore | None = None
        self._memory: MemoryStore | None = None
        self._agent: AgentStore | None = None
        self._root: Path | None = None

    @property
    def root(self) -> Path:
        if self._root is None:
            self._root = resolve_root()
        return self._root

    @property
    def task(self) -> TaskStore:
        if self._task is None:
            self._task = TaskStore(self.root)
        return self._task

    @property
    def project(self) -> ProjectStore:
        if self._project is None:
            self._project = ProjectStore(self.root)
        return self._project

    @property
    def memory(self) -> MemoryStore:
        if self._memory is None:
            self._memory = MemoryStore(self.root)
        return self._memory

    @property
    def agent_store(self) -> AgentStore:
        if self._agent is None:
            self._agent = AgentStore(self.root)
        return self._agent


stores = _Stores()

# In-memory agent registry (agents re-register each session)
agents_registry: dict[str, Agent] = {}

# --- MCP Server ---

mcp = FastMCP(
    "agentpm",
    instructions=(
        "agentpm is a universal project management system for AI coding agents. "
        "Use pm_* tools to manage projects, tasks, memory, and agent coordination. "
        "Tasks are stored as Markdown files with YAML frontmatter in .agentpm/. "
        "Start with pm_board_init to initialize, then pm_project_create to create a project. "
        "Use pm_board_status to see an overview of all projects and tasks."
    ),
)

# Register all tool modules
board.register(mcp, stores, agents_registry)
project.register(mcp, stores, agents_registry)
task.register(mcp, stores, agents_registry)
memory.register(mcp, stores, agents_registry)
agent.register(mcp, stores, agents_registry)
utils.register(mcp, stores, agents_registry)
