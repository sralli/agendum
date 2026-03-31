"""MCP layer tests: project tools."""

from __future__ import annotations

from tests.conftest import call


async def test_project_create_happy(mcp_server):
    mcp, stores, _ = mcp_server
    await call(mcp, "pm_board_init")
    result = await call(mcp, "pm_project_create", name="alpha", description="test project")
    assert "Created project 'alpha'" in result
    assert (stores.root / "projects" / "alpha" / "spec.md").exists()
    assert (stores.root / "projects" / "alpha" / "plan.md").exists()


async def test_project_list_empty(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_project_list")
    assert "No projects" in result


async def test_project_list_shows_projects(mcp_server):
    mcp, _, _ = mcp_server
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="alpha")
    await call(mcp, "pm_project_create", name="beta")
    result = await call(mcp, "pm_project_list")
    assert "alpha" in result
    assert "beta" in result


async def test_project_get_happy(mcp_server):
    mcp, _, _ = mcp_server
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="myproj", description="My description")
    result = await call(mcp, "pm_project_get", project="myproj")
    assert "myproj" in result
    assert "Spec" in result
    assert "Plan" in result


async def test_project_get_not_found(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_project_get", project="nonexistent")
    assert "not found" in result


async def test_spec_update_happy(mcp_server):
    mcp, stores, _ = mcp_server
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="proj")
    result = await call(mcp, "pm_project_spec_update", project="proj", content="# New Spec\n\nUpdated content.")
    assert "Updated spec" in result
    assert "New Spec" in (stores.root / "projects" / "proj" / "spec.md").read_text()


async def test_spec_update_not_found(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_project_spec_update", project="ghost", content="irrelevant")
    assert "Error:" in result


async def test_plan_update_happy(mcp_server):
    mcp, stores, _ = mcp_server
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="proj")
    result = await call(mcp, "pm_project_plan_update", project="proj", content="# New Plan")
    assert "Updated plan" in result
    assert "New Plan" in (stores.root / "projects" / "proj" / "plan.md").read_text()


async def test_plan_update_not_found(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_project_plan_update", project="ghost", content="irrelevant")
    assert "Error:" in result


# --- pm_project_create error path ---


async def test_project_create_invalid_name(mcp_server):
    """pm_project_create: name with path traversal characters returns an Error."""
    mcp, _, _ = mcp_server
    await call(mcp, "pm_board_init")
    result = await call(mcp, "pm_project_create", name="../evil", description="bad")
    assert "Error" in result


# --- pm_project_get additional ---


async def test_project_get_error_invalid_name(mcp_server):
    """pm_project_get: name with traversal chars returns error string."""
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_project_get", project="../../etc/passwd")
    assert "Error" in result or "not found" in result.lower()
