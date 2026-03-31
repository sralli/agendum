"""MCP layer tests: pm_board_init and pm_board_status."""

from __future__ import annotations

from tests.conftest import call


async def test_board_init_creates_structure(mcp_server):
    mcp, stores, _ = mcp_server
    result = await call(mcp, "pm_board_init", name="testboard")
    assert "Initialized" in result
    assert (stores.root / "projects").exists()
    assert (stores.root / "agents").exists()
    assert (stores.root / "memory").exists()
    assert (stores.root / "config.yaml").exists()


async def test_board_init_idempotent(mcp_server):
    mcp, _, _ = mcp_server
    r1 = await call(mcp, "pm_board_init", name="testboard")
    r2 = await call(mcp, "pm_board_init", name="testboard")
    assert "Initialized" in r1
    assert "Initialized" in r2  # no error on second call


async def test_board_status_empty(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_board_status")
    assert "Projects: none" in result
    assert "Total tasks: 0" in result


async def test_board_status_with_project_and_tasks(mcp_server):
    mcp, _, _ = mcp_server
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="myproject", description="test")
    await call(mcp, "pm_task_create", project="myproject", title="Task A")
    await call(mcp, "pm_task_create", project="myproject", title="Task B")

    result = await call(mcp, "pm_board_status")
    assert "myproject" in result
    assert "Total tasks: 2" in result


async def test_board_status_shows_blocked(mcp_server):
    mcp, _, _ = mcp_server
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="proj")
    await call(mcp, "pm_task_create", project="proj", title="Blocker")
    await call(mcp, "pm_task_block", project="proj", task_id="task-001", reason="stuck")

    result = await call(mcp, "pm_board_status")
    assert "task-001" in result


# --- additional coverage ---


async def test_board_init_returns_config_json(mcp_server):
    """pm_board_init: result includes JSON config with the board name."""
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_board_init", name="myboard")
    assert "myboard" in result
    assert "Config:" in result


async def test_board_status_project_not_in_list_after_no_init(mcp_server):
    """pm_board_status: without any projects returns 'none' for projects list."""
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_board_status")
    assert "Projects: none" in result
