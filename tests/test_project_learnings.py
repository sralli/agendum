"""Tests for project-scoped learnings (Feature 1)."""

from __future__ import annotations

from tests.conftest import call


async def test_pm_learn_global(v2_server):
    """pm_learn without project stores in global learnings dir."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    result = await call(mcp, "pm_learn", content="Always pin deps", tags="deps,best-practice")
    assert "learning-001" in result
    assert "global" in result

    learnings = stores.learnings.list_learnings()
    assert len(learnings) == 1
    assert learnings[0]["content"] == "Always pin deps"


async def test_pm_learn_project_scoped(v2_server):
    """pm_learn with project stores in project-specific dir."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("webapp")
    result = await call(mcp, "pm_learn", content="Use barrel exports", tags="typescript,patterns", project="webapp")
    assert "learning-001" in result
    assert "webapp" in result

    # Should be in project learnings, not global
    project_learnings = stores.learnings.list_project_learnings("webapp")
    assert len(project_learnings) == 1
    assert project_learnings[0]["content"] == "Use barrel exports"

    global_learnings = stores.learnings.list_learnings()
    assert len(global_learnings) == 0


async def test_pm_done_with_learnings(v2_server):
    """pm_done with learnings param creates project-scoped learnings."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Setup auth", tags=["auth", "clerk"])

    result = await call(
        mcp,
        "pm_done",
        project="proj",
        item_id="item-001",
        learnings="proxy.ts must be at app level,Always check middleware order",
    )
    assert "done" in result.lower()

    # Should have 2 project-scoped learnings
    project_learnings = stores.learnings.list_project_learnings("proj")
    assert len(project_learnings) == 2
    assert "proxy.ts" in project_learnings[0]["content"]
    # Should inherit item tags
    assert "auth" in project_learnings[0]["tags"]
    assert "clerk" in project_learnings[0]["tags"]


async def test_search_project_learnings(v2_server):
    """search_project_learnings finds project-specific learnings."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")

    stores.learnings.add_learning("barrel exports pattern", ["typescript"], project="proj")
    stores.learnings.add_learning("global pattern", ["typescript"])

    # Project search should only find project-scoped
    results = stores.learnings.search_project_learnings("proj", "barrel")
    assert len(results) == 1
    assert "barrel" in results[0]["content"]

    # Global search should only find global
    results = stores.learnings.search_learnings("global")
    assert len(results) == 1


async def test_project_learnings_enrichment(v2_server):
    """pm_next includes project learnings in context."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")

    # Add a project learning
    stores.learnings.add_learning("Use barrel exports everywhere", ["typescript"], project="proj")

    # Create a task that should pick up the learning
    stores.board.create_item("proj", "Refactor barrel exports", tags=["typescript"])

    result = await call(mcp, "pm_next", project="proj")
    assert "barrel exports" in result.lower()
