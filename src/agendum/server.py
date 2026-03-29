"""agendum MCP server — wires up stores and registers tool modules."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agendum.config import resolve_root
from agendum.models import Agent
from agendum.store.agent_store import AgentStore
from agendum.store.memory_store import MemoryStore
from agendum.store.plan_store import PlanStore
from agendum.store.project_store import ProjectStore
from agendum.store.task_store import TaskStore
from agendum.store.trace_store import TraceStore
from agendum.tools import agent, board, memory, orchestrator, project, task, task_workflow, utils
from agendum.tools.orchestrator.enrichment import ContextEnricher
from agendum.tools.orchestrator.sources import (
    ExternalReferencesSource,
    HandoffSource,
    MemorySource,
    ProjectRulesSource,
    ReviewHistorySource,
)

# --- Lazy store initialization ---


class _Stores:
    """Lazy-initialized stores. Resolves root at first access, not import time."""

    def __init__(self):
        self._task: TaskStore | None = None
        self._project: ProjectStore | None = None
        self._memory: MemoryStore | None = None
        self._agent: AgentStore | None = None
        self._plan: PlanStore | None = None
        self._trace: TraceStore | None = None
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

    @property
    def plan(self) -> PlanStore:
        if self._plan is None:
            self._plan = PlanStore(self.root)
        return self._plan

    @property
    def trace(self) -> TraceStore:
        if self._trace is None:
            self._trace = TraceStore(self.root)
        return self._trace


stores = _Stores()

# In-memory agent registry (agents re-register each session)
agents_registry: dict[str, Agent] = {}

# --- MCP Server ---

mcp = FastMCP(
    "agendum",
    instructions=(
        "agendum is a universal project management system for AI coding agents. "
        "Use pm_* tools to manage projects, tasks, memory, and agent coordination. "
        "Tasks are stored as Markdown files with YAML frontmatter in .agendum/. "
        "Start with pm_board_init to initialize, then pm_project_create to create a project. "
        "Use pm_board_status to see an overview of all projects and tasks."
    ),
)

# --- Context Enrichment Pipeline ---

enricher = ContextEnricher()
enricher.register(ProjectRulesSource(stores.root))
enricher.register(MemorySource(stores.memory))
enricher.register(HandoffSource(stores.task))
enricher.register(ReviewHistorySource())
enricher.register(ExternalReferencesSource(stores.project))

# Register all tool modules
board.register(mcp, stores, agents_registry)
project.register(mcp, stores, agents_registry)
task.register(mcp, stores, agents_registry)
task_workflow.register(mcp, stores, agents_registry)
memory.register(mcp, stores, agents_registry)
agent.register(mcp, stores, agents_registry)
utils.register(mcp, stores, agents_registry)
orchestrator.register(mcp, stores, agents_registry, enricher)
