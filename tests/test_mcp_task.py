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


@pytest.mark.asyncio
async def test_task_create_with_metadata(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(
        mcp,
        "pm_task_create",
        project="proj",
        title="Rich Task",
        review_checklist=["Check lint", "Check tests"],
        test_requirements=["test_auth passes"],
        key_files=["src/auth.py"],
        constraints=["Do not modify config"],
    )
    assert "task-001" in result
    detail = await call(mcp, "pm_task_get", project="proj", task_id="task-001")
    assert "Rich Task" in detail
    assert "Check lint" in detail
    assert "Check tests" in detail
    assert "test_auth passes" in detail
    assert "src/auth.py" in detail
    assert "Do not modify config" in detail


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


# --- pm_task_archive ---


@pytest.mark.asyncio
async def test_task_archive_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Done task")
    await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    # Task is auto-archived on complete, so it won't be in active list
    result = await call(mcp, "pm_task_list", project="proj")
    assert "task-001" not in result or "No tasks found" in result
    # But accessible via get
    result = await call(mcp, "pm_task_get", project="proj", task_id="task-001")
    assert "Done task" in result


@pytest.mark.asyncio
async def test_task_archive_pending_fails(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Pending task")
    result = await call(mcp, "pm_task_archive", project="proj", task_id="task-001")
    assert "Error" in result


@pytest.mark.asyncio
async def test_task_archive_all(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="A")
    await call(mcp, "pm_task_create", project="proj", title="B")
    await call(mcp, "pm_task_create", project="proj", title="C")
    # Complete first two (auto-archives them)
    await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    await call(mcp, "pm_task_complete", project="proj", task_id="task-002")
    # Only task-003 should be active
    result = await call(mcp, "pm_task_list", project="proj")
    assert "task-003" in result
    assert "task-001" not in result
    assert "task-002" not in result


@pytest.mark.asyncio
async def test_task_archive_all_nothing_to_archive(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Pending")
    result = await call(mcp, "pm_task_archive_all", project="proj")
    assert "No done/cancelled" in result


@pytest.mark.asyncio
async def test_task_list_include_archived(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="A")
    await call(mcp, "pm_task_create", project="proj", title="B")
    await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    # Without include_archived: only task-002
    result = await call(mcp, "pm_task_list", project="proj")
    assert "task-002" in result
    assert "task-001" not in result
    # With include_archived: both
    result = await call(mcp, "pm_task_list", project="proj", include_archived=True)
    assert "task-001" in result
    assert "task-002" in result


@pytest.mark.asyncio
async def test_task_unarchive(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Restore me")
    await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    # Unarchive
    result = await call(mcp, "pm_task_unarchive", project="proj", task_id="task-001")
    assert "Unarchived" in result
    assert "Restore me" in result
    # Now visible in active list again
    result = await call(mcp, "pm_task_list", project="proj")
    assert "task-001" in result


@pytest.mark.asyncio
async def test_task_unarchive_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_unarchive", project="proj", task_id="task-999")
    assert "Error" in result


@pytest.mark.asyncio
async def test_task_complete_auto_archives(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Auto archive me")
    result = await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    assert "archived" in result
    # Not in active list
    list_result = await call(mcp, "pm_task_list", project="proj")
    assert "task-001" not in list_result or "No tasks found" in list_result
