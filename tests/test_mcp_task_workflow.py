"""MCP layer tests: task workflow tools (claim, progress, complete, block, handoff, next)."""

from __future__ import annotations

import pytest

from tests.conftest import call


async def _setup(mcp) -> None:
    """Initialize board and create a test project."""
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="proj")


# --- pm_task_claim ---


@pytest.mark.asyncio
async def test_task_claim_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Claimable")
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-001", agent_id="agent-x")
    assert "Claimed task-001" in result
    assert "in_progress" in result


@pytest.mark.asyncio
async def test_task_claim_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-999", agent_id="agent-x")
    assert "not found" in result


@pytest.mark.asyncio
async def test_task_claim_already_in_progress(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Claimable")
    await call(mcp, "pm_task_claim", project="proj", task_id="task-001", agent_id="agent-a")
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-001", agent_id="agent-b")
    assert "cannot claim" in result


@pytest.mark.asyncio
async def test_task_claim_unmet_deps(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="First")
    await call(mcp, "pm_task_create", project="proj", title="Second", depends_on=["task-001"])
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-002", agent_id="agent-x")
    assert "unmet dependencies" in result


# --- pm_task_progress ---


@pytest.mark.asyncio
async def test_task_progress_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Task")
    result = await call(
        mcp, "pm_task_progress", project="proj", task_id="task-001", message="did something", agent_id="agent-1"
    )
    assert "Logged progress" in result
    assert "did something" in result


@pytest.mark.asyncio
async def test_task_progress_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_progress", project="proj", task_id="task-999", message="oops")
    assert "not found" in result


# --- pm_task_complete ---


@pytest.mark.asyncio
async def test_task_complete_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Task")
    result = await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    assert "Completed task-001" in result


@pytest.mark.asyncio
async def test_task_complete_auto_unblocks(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="First")
    await call(mcp, "pm_task_create", project="proj", title="Second", depends_on=["task-001"])
    await call(mcp, "pm_task_block", project="proj", task_id="task-002", reason="waiting for task-001")
    result = await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    assert "Unblocked" in result
    assert "task-002" in result


@pytest.mark.asyncio
async def test_task_complete_with_criteria_warning(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Task", acceptance_criteria=["check this"])
    result = await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    assert "acceptance criteria" in result


@pytest.mark.asyncio
async def test_task_complete_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_complete", project="proj", task_id="task-999")
    assert "not found" in result


# --- pm_task_block ---


@pytest.mark.asyncio
async def test_task_block_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Task")
    result = await call(mcp, "pm_task_block", project="proj", task_id="task-001", reason="waiting on external API")
    assert "Blocked task-001" in result
    assert "waiting on external API" in result


@pytest.mark.asyncio
async def test_task_block_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_block", project="proj", task_id="task-999", reason="whatever")
    assert "not found" in result


# --- pm_task_handoff ---


@pytest.mark.asyncio
async def test_task_handoff_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Task")
    result = await call(
        mcp,
        "pm_task_handoff",
        project="proj",
        task_id="task-001",
        handoff_context="Done X, still need Y",
        agent_id="agent-1",
    )
    assert "Handoff context saved" in result
    detail = await call(mcp, "pm_task_get", project="proj", task_id="task-001")
    assert "Done X, still need Y" in detail


@pytest.mark.asyncio
async def test_task_handoff_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_handoff", project="proj", task_id="task-999", handoff_context="irrelevant")
    assert "not found" in result


# --- pm_task_next ---


@pytest.mark.asyncio
async def test_task_next_suggests_highest_priority(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Low", priority="low")
    await call(mcp, "pm_task_create", project="proj", title="High", priority="high")
    result = await call(mcp, "pm_task_next", project="proj")
    assert "High" in result


@pytest.mark.asyncio
async def test_task_next_no_tasks(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_next", project="proj")
    assert "No tasks available" in result


@pytest.mark.asyncio
async def test_task_next_invalid_project(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_next", project="../../nope")
    assert "Error" in result


# --- pm_task_handoff structured ---


@pytest.mark.asyncio
async def test_task_handoff_structured_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Structured handoff task")
    result = await call(
        mcp,
        "pm_task_handoff",
        project="proj",
        task_id="task-001",
        agent_id="agent-1",
        completed=["Set up database schema", "Added migrations"],
        remaining=["Write integration tests", "Update docs"],
        key_files=["src/db/schema.py", "migrations/001.sql"],
        decisions=["Chose SQLite for simplicity"],
        gotchas=["Connection pool must be closed before fork"],
    )
    assert "Handoff context saved" in result
    assert "Done: 2 items" in result
    assert "remaining: 2 items" in result
    detail = await call(mcp, "pm_task_get", project="proj", task_id="task-001")
    assert "Set up database schema" in detail
    assert "Write integration tests" in detail


# --- archive + dependency interaction ---


@pytest.mark.asyncio
async def test_claim_after_dependency_archived(mcp_server):
    """Claiming a task must work even if its dependency was auto-archived."""
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="First")
    await call(mcp, "pm_task_create", project="proj", title="Second", depends_on=["task-001"])
    # Complete task-001 (auto-archives it)
    result = await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    assert "archived" in result
    # Claim task-002 — should succeed despite task-001 being archived
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-002", agent_id="agent-1")
    assert "Claimed task-002" in result


@pytest.mark.asyncio
async def test_complete_chain_with_archived_deps(mcp_server):
    """Completing a task unblocks dependents even when earlier deps are archived."""
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="First")
    await call(mcp, "pm_task_create", project="proj", title="Second")
    await call(mcp, "pm_task_create", project="proj", title="Third", depends_on=["task-001", "task-002"])
    # Block task-003 explicitly
    await call(mcp, "pm_task_block", project="proj", task_id="task-003", reason="waiting")
    # Complete task-001 (auto-archives)
    await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    # Complete task-002 — should unblock task-003 even though task-001 is archived
    result = await call(mcp, "pm_task_complete", project="proj", task_id="task-002")
    assert "Unblocked: task-003" in result


@pytest.mark.asyncio
async def test_next_with_archived_deps(mcp_server):
    """suggest_next_task works when dependencies are archived."""
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="First")
    await call(mcp, "pm_task_create", project="proj", title="Second", depends_on=["task-001"])
    # Complete task-001 (auto-archives)
    await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    # pm_task_next should suggest task-002
    result = await call(mcp, "pm_task_next", project="proj")
    assert "Second" in result


# --- pm_check_deps + archived dependencies ---


@pytest.mark.asyncio
async def test_check_deps_recognizes_archived_deps(mcp_server):
    """pm_check_deps shows task-002 as unblocked when its dep (task-001) is archived."""
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="First")
    await call(mcp, "pm_task_create", project="proj", title="Second", depends_on=["task-001"])
    # Complete task-001 (auto-archives it)
    await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    # pm_check_deps should show task-002 as ready (unblocked)
    result = await call(mcp, "pm_check_deps", project="proj")
    assert "task-002" in result
    assert "Ready to start" in result
