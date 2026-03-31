"""MCP layer tests: pm_check_deps utility tool."""

from __future__ import annotations

from tests.conftest import call


async def _init(mcp) -> None:
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="proj")


async def test_check_deps_empty_project(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    result = await call(mcp, "pm_check_deps", project="proj")
    assert "Total tasks: 0" in result
    assert "No dependency cycles" in result


async def test_check_deps_shows_ready_tasks(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Ready task")
    await call(mcp, "pm_task_create", project="proj", title="Blocked task", depends_on=["task-001"])
    result = await call(mcp, "pm_check_deps", project="proj")
    assert "Ready to start: 1" in result
    assert "task-001" in result


async def test_check_deps_no_cycles(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    await call(mcp, "pm_task_create", project="proj", title="A")
    await call(mcp, "pm_task_create", project="proj", title="B", depends_on=["task-001"])
    result = await call(mcp, "pm_check_deps", project="proj")
    assert "No dependency cycles" in result


async def test_check_deps_total_count(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    for i in range(3):
        await call(mcp, "pm_task_create", project="proj", title=f"Task {i}")
    result = await call(mcp, "pm_check_deps", project="proj")
    assert "Total tasks: 3" in result


# --- pm_check_deps error path ---


async def test_check_deps_invalid_project(mcp_server):
    """pm_check_deps: invalid project name (path traversal) returns Error."""
    mcp, _, _ = mcp_server
    await _init(mcp)
    result = await call(mcp, "pm_check_deps", project="../../nope")
    assert "Error" in result
