"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from mcp.server.fastmcp import FastMCP

from agentpm.server import _Stores
from agentpm.tools import agent, board, memory, project, task, utils


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Create a temporary .agentpm root directory."""
    root = tmp_path / ".agentpm"
    root.mkdir()
    return root


@pytest_asyncio.fixture
async def mcp_server(tmp_path: Path):
    """Fresh FastMCP instance with isolated stores, wired for all tool modules."""
    root = tmp_path / ".agentpm"
    root.mkdir()

    stores = _Stores()
    stores._root = root  # bypass resolve_root()

    agents_registry: dict = {}

    mcp = FastMCP("agentpm-test")
    board.register(mcp, stores, agents_registry)
    project.register(mcp, stores, agents_registry)
    task.register(mcp, stores, agents_registry)
    memory.register(mcp, stores, agents_registry)
    agent.register(mcp, stores, agents_registry)
    utils.register(mcp, stores, agents_registry)

    return mcp, stores, agents_registry


async def call(mcp: FastMCP, tool_name: str, **kwargs) -> str:
    """Call an MCP tool and return the text result."""
    content, _ = await mcp.call_tool(tool_name, kwargs)
    return content[0].text
