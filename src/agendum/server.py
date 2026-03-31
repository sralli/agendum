"""agendum MCP server — Project Memory + Scoping Engine."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agendum.config import resolve_root
from agendum.enrichment.pipeline import ContextEnricher
from agendum.enrichment.sources import DependencySource, MemorySource, ProjectRulesSource
from agendum.store.board_store import BoardStore
from agendum.store.learnings_store import LearningsStore
from agendum.store.memory_store import MemoryStore
from agendum.store.project_store import ProjectStore
from agendum.tools import register


class _Stores:
    """Lazy-initialized stores — resolve root at first access."""

    def __init__(self) -> None:
        self._root: Path | None = None
        self._board: BoardStore | None = None
        self._project: ProjectStore | None = None
        self._memory: MemoryStore | None = None
        self._learnings: LearningsStore | None = None

    @property
    def root(self) -> Path:
        if self._root is None:
            self._root = resolve_root()
        return self._root

    @property
    def board(self) -> BoardStore:
        if self._board is None:
            self._board = BoardStore(self.root)
        return self._board

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
    def learnings(self) -> LearningsStore:
        if self._learnings is None:
            self._learnings = LearningsStore(self.root)
        return self._learnings


stores = _Stores()


class _LazyEnricher:
    """Defers enrichment source registration until first use."""

    def __init__(self) -> None:
        self._inner: ContextEnricher | None = None

    def _init(self) -> ContextEnricher:
        if self._inner is None:
            self._inner = ContextEnricher()
            self._inner.register(ProjectRulesSource(stores.root))
            self._inner.register(MemorySource(stores.memory))
            self._inner.register(DependencySource(stores.board))
        return self._inner

    def enrich(self, *args, **kwargs):
        return self._init().enrich(*args, **kwargs)


enricher = _LazyEnricher()

INSTRUCTIONS = """agendum is a project memory and scoping engine for AI coding agents.
Use pm_* tools to manage projects, board items, memory, and work packages.
Start with pm_init to initialize, then pm_project to create a project.
Use pm_status to see an overview. Use pm_add to add items to the board.
Use pm_ingest to import a plan file. Use pm_next to get scoped work packages.
Use pm_done to report completion. Use pm_learn for cross-project learnings."""

mcp = FastMCP("agendum", instructions=INSTRUCTIONS)
register(mcp, stores, enricher)
