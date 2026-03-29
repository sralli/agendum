"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from mcp.server.fastmcp import FastMCP

from agendum.server import _Stores
from agendum.store.plan_store import PlanStore
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
    stores._plan = PlanStore(root)
    stores._trace = TraceStore(root)

    agents_registry: dict = {}

    # Build enricher with all sources
    enricher = ContextEnricher()
    enricher.register(ProjectRulesSource(root))
    enricher.register(MemorySource(stores.memory))
    enricher.register(HandoffSource(stores.task))
    enricher.register(ReviewHistorySource())
    enricher.register(ExternalReferencesSource(stores.project))

    mcp = FastMCP("agentpm-test")
    board.register(mcp, stores, agents_registry)
    project.register(mcp, stores, agents_registry)
    task.register(mcp, stores, agents_registry)
    task_workflow.register(mcp, stores, agents_registry)
    memory.register(mcp, stores, agents_registry)
    agent.register(mcp, stores, agents_registry)
    utils.register(mcp, stores, agents_registry)
    orchestrator.register(mcp, stores, agents_registry, enricher)

    return mcp, stores, agents_registry


async def call(mcp: FastMCP, tool_name: str, **kwargs) -> str:
    """Call an MCP tool and return the text result."""
    content, _ = await mcp.call_tool(tool_name, kwargs)
    return content[0].text


# --- Orchestrator test helpers ---

import json  # noqa: E402


@pytest_asyncio.fixture
async def setup(mcp_server):
    """Create a project for orchestrator tests."""
    mcp, stores, agents = mcp_server
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="myapp", description="Test app")
    return mcp, stores, agents


def _tasks_json(tasks: list[dict]) -> str:
    return json.dumps(tasks)


async def _create_and_approve(mcp, project, goal, tasks, **kwargs):
    """Create a plan and approve it for execution."""
    result = await call(
        mcp,
        "pm_orchestrate_plan",
        project=project,
        goal=goal,
        tasks_json=_tasks_json(tasks),
        **kwargs,
    )
    plan_id = "plan-001"
    for line in result.splitlines():
        if "Plan Created:" in line:
            plan_id = line.split("Plan Created:")[1].strip()
            break
    await call(mcp, "pm_orchestrate_approve", project=project, plan_id=plan_id)
    return result, plan_id
