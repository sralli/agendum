"""MCP layer tests: task CRUD tools (create, list, get)."""

from __future__ import annotations

from tests.conftest import call

# --- pm_task_create ---


async def test_task_create_happy(setup):
    mcp, _, _ = setup
    result = await call(mcp, "pm_task_create", project="myapp", title="My Task")
    assert "Created task task-001" in result


async def test_task_create_with_deps(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="First")
    result = await call(mcp, "pm_task_create", project="myapp", title="Second", depends_on=["task-001"])
    assert "task-002" in result
    assert "blocked by" in result


async def test_task_create_with_metadata(setup):
    mcp, _, _ = setup
    result = await call(
        mcp,
        "pm_task_create",
        project="myapp",
        title="Rich Task",
        review_checklist=["Check lint", "Check tests"],
        test_requirements=["test_auth passes"],
        key_files=["src/auth.py"],
        constraints=["Do not modify config"],
    )
    assert "task-001" in result
    detail = await call(mcp, "pm_task_get", project="myapp", task_id="task-001")
    assert "Rich Task" in detail
    assert "Check lint" in detail
    assert "Check tests" in detail
    assert "test_auth passes" in detail
    assert "src/auth.py" in detail
    assert "Do not modify config" in detail


# --- pm_task_list ---


async def test_task_list_happy(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="A")
    await call(mcp, "pm_task_create", project="myapp", title="B")
    result = await call(mcp, "pm_task_list", project="myapp")
    assert "Tasks in 'myapp' (2)" in result
    assert "task-001" in result
    assert "task-002" in result


async def test_task_list_filter_status(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="A")
    result = await call(mcp, "pm_task_list", project="myapp", status="pending")
    assert "task-001" in result


async def test_task_list_invalid_status(setup):
    mcp, _, _ = setup
    result = await call(mcp, "pm_task_list", project="myapp", status="bogus")
    assert "Invalid status" in result


async def test_task_list_empty(setup):
    mcp, _, _ = setup
    result = await call(mcp, "pm_task_list", project="myapp")
    assert "No tasks found" in result


# --- pm_task_get ---


async def test_task_get_happy(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="My Task", acceptance_criteria=["criterion one"])
    result = await call(mcp, "pm_task_get", project="myapp", task_id="task-001")
    assert "My Task" in result
    assert "criterion one" in result


async def test_task_get_not_found(setup):
    mcp, _, _ = setup
    result = await call(mcp, "pm_task_get", project="myapp", task_id="task-999")
    assert "not found" in result


# --- error paths ---


async def test_task_create_invalid_project_name(setup):
    mcp, _, _ = setup
    result = await call(mcp, "pm_task_create", project="../evil", title="Bad task")
    assert "Error" in result


# --- pm_task_archive ---


async def test_task_archive_happy(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="Done task")
    await call(mcp, "pm_task_complete", project="myapp", task_id="task-001")
    # Task is auto-archived on complete, so it won't be in active list
    result = await call(mcp, "pm_task_list", project="myapp")
    assert "task-001" not in result or "No tasks found" in result
    # But accessible via get
    result = await call(mcp, "pm_task_get", project="myapp", task_id="task-001")
    assert "Done task" in result


async def test_task_archive_pending_fails(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="Pending task")
    result = await call(mcp, "pm_task_archive", project="myapp", task_id="task-001")
    assert "Error" in result


async def test_task_archive_all(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="A")
    await call(mcp, "pm_task_create", project="myapp", title="B")
    await call(mcp, "pm_task_create", project="myapp", title="C")
    # Complete first two (auto-archives them)
    await call(mcp, "pm_task_complete", project="myapp", task_id="task-001")
    await call(mcp, "pm_task_complete", project="myapp", task_id="task-002")
    # Only task-003 should be active
    result = await call(mcp, "pm_task_list", project="myapp")
    assert "task-003" in result
    assert "task-001" not in result
    assert "task-002" not in result


async def test_task_archive_all_nothing_to_archive(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="Pending")
    result = await call(mcp, "pm_task_archive_all", project="myapp")
    assert "No done/cancelled" in result


async def test_task_list_include_archived(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="A")
    await call(mcp, "pm_task_create", project="myapp", title="B")
    await call(mcp, "pm_task_complete", project="myapp", task_id="task-001")
    # Without include_archived: only task-002
    result = await call(mcp, "pm_task_list", project="myapp")
    assert "task-002" in result
    assert "task-001" not in result
    # With include_archived: both
    result = await call(mcp, "pm_task_list", project="myapp", include_archived=True)
    assert "task-001" in result
    assert "task-002" in result


async def test_task_complete_auto_archives(setup):
    mcp, _, _ = setup
    await call(mcp, "pm_task_create", project="myapp", title="Auto archive me")
    result = await call(mcp, "pm_task_complete", project="myapp", task_id="task-001")
    assert "archived" in result
    # Not in active list
    list_result = await call(mcp, "pm_task_list", project="myapp")
    assert "task-001" not in list_result or "No tasks found" in list_result
