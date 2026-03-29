"""MCP layer tests: task CRUD tools (create, list, get)."""

from __future__ import annotations

import pytest

from tests.conftest import call


async def _setup(mcp) -> None:
    """Initialize board and create a test project."""
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="proj")


# --- pm_task_create ---


@pytest.mark.asyncio
async def test_task_create_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_create", project="proj", title="My Task")
    assert "Created task task-001" in result


@pytest.mark.asyncio
async def test_task_create_with_deps(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="First")
    result = await call(mcp, "pm_task_create", project="proj", title="Second", depends_on=["task-001"])
    assert "task-002" in result
    assert "blocked by" in result


# --- pm_task_list ---


@pytest.mark.asyncio
async def test_task_list_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="A")
    await call(mcp, "pm_task_create", project="proj", title="B")
    result = await call(mcp, "pm_task_list", project="proj")
    assert "Tasks in 'proj' (2)" in result
    assert "task-001" in result
    assert "task-002" in result


@pytest.mark.asyncio
async def test_task_list_filter_status(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="A")
    result = await call(mcp, "pm_task_list", project="proj", status="pending")
    assert "task-001" in result


@pytest.mark.asyncio
async def test_task_list_invalid_status(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_list", project="proj", status="bogus")
    assert "Invalid status" in result


@pytest.mark.asyncio
async def test_task_list_empty(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_list", project="proj")
    assert "No tasks found" in result


# --- pm_task_get ---


@pytest.mark.asyncio
async def test_task_get_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="My Task", acceptance_criteria=["criterion one"])
    result = await call(mcp, "pm_task_get", project="proj", task_id="task-001")
    assert "My Task" in result
    assert "criterion one" in result


@pytest.mark.asyncio
async def test_task_get_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_get", project="proj", task_id="task-999")
    assert "not found" in result


# --- error paths ---


@pytest.mark.asyncio
async def test_task_create_invalid_project_name(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_create", project="../evil", title="Bad task")
    assert "Error" in result
