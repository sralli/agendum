"""MCP layer tests: all 8 task tools."""

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
    result = await call(mcp, "pm_task_create", project="proj", title="Second",
                        depends_on=["task-001"])
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
    await call(mcp, "pm_task_create", project="proj", title="My Task",
               acceptance_criteria=["criterion one"])
    result = await call(mcp, "pm_task_get", project="proj", task_id="task-001")
    assert "My Task" in result
    assert "criterion one" in result


@pytest.mark.asyncio
async def test_task_get_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_get", project="proj", task_id="task-999")
    assert "not found" in result


# --- pm_task_claim ---

@pytest.mark.asyncio
async def test_task_claim_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Claimable")
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-001",
                        agent_id="agent-x")
    assert "Claimed task-001" in result
    assert "in_progress" in result


@pytest.mark.asyncio
async def test_task_claim_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-999",
                        agent_id="agent-x")
    assert "not found" in result


@pytest.mark.asyncio
async def test_task_claim_already_in_progress(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Claimable")
    await call(mcp, "pm_task_claim", project="proj", task_id="task-001", agent_id="agent-a")
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-001",
                        agent_id="agent-b")
    assert "cannot claim" in result


@pytest.mark.asyncio
async def test_task_claim_unmet_deps(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="First")
    await call(mcp, "pm_task_create", project="proj", title="Second", depends_on=["task-001"])
    result = await call(mcp, "pm_task_claim", project="proj", task_id="task-002",
                        agent_id="agent-x")
    assert "unmet dependencies" in result


# --- pm_task_progress ---

@pytest.mark.asyncio
async def test_task_progress_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Task")
    result = await call(mcp, "pm_task_progress", project="proj", task_id="task-001",
                        message="did something", agent_id="agent-1")
    assert "Logged progress" in result
    assert "did something" in result


@pytest.mark.asyncio
async def test_task_progress_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_progress", project="proj", task_id="task-999",
                        message="oops")
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
    # Explicitly block task-002 so resolve_completions can unblock it
    await call(mcp, "pm_task_block", project="proj", task_id="task-002", reason="waiting for task-001")
    result = await call(mcp, "pm_task_complete", project="proj", task_id="task-001")
    assert "Unblocked" in result
    assert "task-002" in result


@pytest.mark.asyncio
async def test_task_complete_with_criteria_warning(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Task",
               acceptance_criteria=["check this"])
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
    result = await call(mcp, "pm_task_block", project="proj", task_id="task-001",
                        reason="waiting on external API")
    assert "Blocked task-001" in result
    assert "waiting on external API" in result


@pytest.mark.asyncio
async def test_task_block_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_block", project="proj", task_id="task-999",
                        reason="whatever")
    assert "not found" in result


# --- pm_task_handoff ---

@pytest.mark.asyncio
async def test_task_handoff_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Task")
    result = await call(mcp, "pm_task_handoff", project="proj", task_id="task-001",
                        handoff_context="Done X, still need Y", agent_id="agent-1")
    assert "Handoff context saved" in result
    # Verify it's visible in task get
    detail = await call(mcp, "pm_task_get", project="proj", task_id="task-001")
    assert "Done X, still need Y" in detail


@pytest.mark.asyncio
async def test_task_handoff_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_handoff", project="proj", task_id="task-999",
                        handoff_context="irrelevant")
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


# --- pm_task_create error path ---

@pytest.mark.asyncio
async def test_task_create_invalid_project_name(mcp_server):
    """pm_task_create: project name with path traversal returns Error."""
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_create", project="../evil", title="Bad task")
    assert "Error" in result


# --- pm_task_next error path ---

@pytest.mark.asyncio
async def test_task_next_invalid_project(mcp_server):
    """pm_task_next: invalid project name returns Error."""
    mcp, _, _ = mcp_server
    await _setup(mcp)
    result = await call(mcp, "pm_task_next", project="../../nope")
    assert "Error" in result


# --- pm_task_handoff structured happy path ---

@pytest.mark.asyncio
async def test_task_handoff_structured_happy(mcp_server):
    """pm_task_handoff: structured format with completed/remaining lists is saved."""
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
