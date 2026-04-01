"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from mcp.server.fastmcp import FastMCP


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Create a temporary .agendum root directory."""
    root = tmp_path / ".agendum"
    root.mkdir()
    return root


async def call(mcp: FastMCP, tool_name: str, **kwargs) -> str:
    """Call an MCP tool and return the first text content."""
    content, _ = await mcp.call_tool(tool_name, kwargs)
    return content[0].text


@pytest_asyncio.fixture
async def v2_server(tmp_path):
    """Fresh FastMCP instance with v2 stores and tools."""
    root = tmp_path / ".agendum"
    root.mkdir()

    from agendum.enrichment.pipeline import ContextEnricher
    from agendum.enrichment.sources import DependencySource, MemorySource, ProjectLearningsSource, ProjectRulesSource
    from agendum.store.board_store import BoardStore
    from agendum.store.learnings_store import LearningsStore
    from agendum.store.memory_store import MemoryStore
    from agendum.store.project_store import ProjectStore

    class Stores:
        def __init__(self, root):
            self._root = root
            self.board = BoardStore(root)
            self.project = ProjectStore(root)
            self.memory = MemoryStore(root)
            self.learnings = LearningsStore(root)

        @property
        def root(self):
            return self._root

    stores = Stores(root)

    enricher = ContextEnricher()
    enricher.register(ProjectRulesSource(root))
    enricher.register(MemorySource(stores.memory))
    enricher.register(DependencySource(stores.board))
    enricher.register(ProjectLearningsSource(stores.learnings))

    mcp = FastMCP("agendum-test-v2")
    from agendum.tools import register

    register(mcp, stores, enricher)

    return mcp, stores
