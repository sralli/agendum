"""Integration tests for the 11 v2 MCP tools."""

from __future__ import annotations

from tests.conftest import call


async def test_pm_init(v2_server):
    mcp, stores = v2_server
    result = await call(mcp, "pm_init", name="myboard")
    assert "initialized" in result.lower()


async def test_pm_project_create(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    result = await call(mcp, "pm_project", action="create", name="webapp", description="A web app")
    assert "webapp" in result
    assert "created" in result.lower()


async def test_pm_project_list(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("alpha")
    stores.project.create_project("beta")
    result = await call(mcp, "pm_project", action="list")
    assert "alpha" in result
    assert "beta" in result


async def test_pm_project_get(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("webapp", "A web application")
    result = await call(mcp, "pm_project", action="get", name="webapp")
    assert "webapp" in result
    assert "Spec excerpt" in result


async def test_pm_add(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    result = await call(mcp, "pm_add", project="proj", title="Setup CI")
    assert "item-001" in result
    assert "Setup CI" in result


async def test_pm_add_with_metadata(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    result = await call(
        mcp,
        "pm_add",
        project="proj",
        title="Deploy",
        priority="high",
        tags="infra,ci",
        acceptance_criteria="deploys successfully,no downtime",
        key_files="deploy.sh,Dockerfile",
    )
    assert "item-001" in result

    item = stores.board.get_item("proj", "item-001")
    assert item is not None
    assert item.priority.value == "high"
    assert "infra" in item.tags
    assert "ci" in item.tags
    assert len(item.acceptance_criteria) == 2
    assert len(item.key_files) == 2


async def test_pm_board(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")
    stores.board.create_item("proj", "Task B")
    result = await call(mcp, "pm_board", project="proj")
    assert "Task A" in result
    assert "Task B" in result
    assert "| ID |" in result


async def test_pm_status(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")
    stores.board.create_item("proj", "Task B")
    result = await call(mcp, "pm_status", project="proj")
    assert "pending" in result
    assert "Suggested Next" in result


async def test_pm_status_all_projects(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj1")
    stores.project.create_project("proj2")
    stores.board.create_item("proj1", "Task 1")
    result = await call(mcp, "pm_status")
    assert "proj1" in result
    assert "proj2" in result


async def test_pm_next(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Build API", key_files=["src/api.py"], acceptance_criteria=["API works"])
    result = await call(mcp, "pm_next", project="proj")
    assert "Build API" in result
    assert "src/api.py" in result
    assert "API works" in result

    # Verify item is now in_progress
    item = stores.board.get_item("proj", "item-001")
    assert item is not None
    assert item.status.value == "in_progress"


async def test_pm_next_includes_complexity(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item(
        "proj",
        "Big refactor",
        key_files=["a.py", "b.py", "c.py", "d.py"],
        acceptance_criteria=["passes tests", "no regressions", "docs updated"],
    )
    result = await call(mcp, "pm_next", project="proj")
    assert "Complexity:" in result
    assert "4-file" in result


async def test_pm_next_no_tasks(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    result = await call(mcp, "pm_next", project="proj")
    assert "No tasks available" in result


async def test_pm_done_updates_memory(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Setup auth")

    result = await call(
        mcp,
        "pm_done",
        project="proj",
        item_id="item-001",
        decisions="Use JWT tokens,Session expiry 24h",
        files_changed="src/auth.py",
    )
    assert "done" in result.lower()

    # Check decisions were written to memory
    decisions = stores.memory.read("decisions")
    assert "JWT tokens" in decisions
    assert "Session expiry 24h" in decisions

    # Check item is done
    item = stores.board.get_item("proj", "item-001")
    assert item is not None
    assert item.status.value == "done"
    assert "Use JWT tokens" in item.decisions


async def test_pm_done_unblocks(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    from agendum.models import TaskStatus

    stores.board.create_item("proj", "Task A")
    stores.board.create_item("proj", "Task B", depends_on=["item-001"], status=TaskStatus.BLOCKED)

    result = await call(mcp, "pm_done", project="proj", item_id="item-001")
    assert "Unblocked" in result
    assert "item-002" in result

    # Verify item-002 is now pending
    item_b = stores.board.get_item("proj", "item-002")
    assert item_b is not None
    assert item_b.status.value == "pending"


async def test_pm_block(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")

    result = await call(mcp, "pm_block", project="proj", item_id="item-001", reason="Waiting for API key")
    assert "Blocked" in result
    assert "Waiting for API key" in result

    item = stores.board.get_item("proj", "item-001")
    assert item is not None
    assert item.status.value == "blocked"


async def test_pm_memory_append_and_read(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")

    await call(mcp, "pm_memory", action="append", scope="decisions", content="Use PostgreSQL")
    await call(mcp, "pm_memory", action="append", scope="decisions", content="REST over GraphQL", author="dev")

    result = await call(mcp, "pm_memory", action="read", scope="decisions")
    assert "PostgreSQL" in result
    assert "REST over GraphQL" in result


async def test_pm_memory_search(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")

    stores.memory.append("decisions", "Use PostgreSQL for persistence")
    stores.memory.append("patterns", "Repository pattern for data access")

    result = await call(mcp, "pm_memory", action="search", query="PostgreSQL")
    assert "PostgreSQL" in result
    assert "decisions" in result


async def test_pm_learn(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")

    result = await call(
        mcp, "pm_learn", content="Always pin dependency versions", tags="deps,best-practice", source_project="webapp"
    )
    assert "learning-001" in result
    assert "added" in result.lower()


async def test_pm_ingest(v2_server, tmp_path):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")

    plan_content = """\
## Task 1: Install SDK
- Install the package

**Acceptance Criteria:**
- Package installed
- Config file created

**Files:** src/config.ts

## Task 2: Create pages
- Build the pages

**Acceptance Criteria:**
- Pages render correctly

**Files:** src/pages/index.tsx, src/pages/about.tsx
**Depends:** Task 1

## Task 3: Add middleware
- Protect routes

**Acceptance Criteria:**
- Auth check works

**Files:** src/proxy.ts
**Depends:** Task 1, Task 2
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content)

    result = await call(mcp, "pm_ingest", project="proj", plan_file=str(plan_file))
    assert "3 items" in result
    assert "Dependency levels" in result

    # Verify items were created
    items = stores.board.list_items("proj")
    assert len(items) == 3

    # Check item-001
    item1 = stores.board.get_item("proj", "item-001")
    assert item1 is not None
    assert item1.title == "Install SDK"
    assert "src/config.ts" in item1.key_files
    assert len(item1.acceptance_criteria) == 2

    # Check item-003 depends on item-001 and item-002
    item3 = stores.board.get_item("proj", "item-003")
    assert item3 is not None
    assert "item-001" in item3.depends_on
    assert "item-002" in item3.depends_on


# ── Feature 7: Verification Gate ──────────────────────────────────────


async def test_pm_done_verified(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")
    result = await call(
        mcp,
        "pm_done",
        project="proj",
        item_id="item-001",
        verified=True,
        verification_notes="All tests pass",
        auto_extract=False,
    )
    assert "done" in result.lower()
    item = stores.board.get_item("proj", "item-001")
    assert item.verified is True
    # Check progress has "Verified"
    assert any("Verified" in p.message for p in item.progress)
    assert any("All tests pass" in p.message for p in item.progress)


async def test_pm_done_unverified(v2_server):
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")
    result = await call(
        mcp,
        "pm_done",
        project="proj",
        item_id="item-001",
        auto_extract=False,
    )
    assert "done" in result.lower()
    item = stores.board.get_item("proj", "item-001")
    assert item.verified is False
    assert any("Unverified" in p.message for p in item.progress)


async def test_pm_done_verified_persists_through_save_load(v2_server):
    """verified field must survive serialization round-trip."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")
    await call(
        mcp,
        "pm_done",
        project="proj",
        item_id="item-001",
        verified=True,
        auto_extract=False,
    )
    # Re-read from disk
    item = stores.board.get_item("proj", "item-001")
    assert item.verified is True


# ── Feature 9: Auto-Extract from Git ──────────────────────────────────


async def test_pm_done_auto_extract_no_git(v2_server):
    """auto_extract gracefully handles non-git environment."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")
    # This should work even without git — graceful fallback
    result = await call(
        mcp,
        "pm_done",
        project="proj",
        item_id="item-001",
        auto_extract=True,
    )
    assert "done" in result.lower()


async def test_pm_done_auto_extract_skipped_when_files_provided(v2_server):
    """When files_changed is provided, auto_extract should not override it."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")
    result = await call(
        mcp,
        "pm_done",
        project="proj",
        item_id="item-001",
        files_changed="manual.py",
        auto_extract=True,
    )
    assert "done" in result.lower()
    item = stores.board.get_item("proj", "item-001")
    assert any("manual.py" in p.message for p in item.progress)


async def test_pm_next_hints_verification(v2_server):
    """pm_next output should hint about verified=True."""
    mcp, stores = v2_server
    stores.project.init_board("test")
    stores.project.create_project("proj")
    stores.board.create_item("proj", "Task A")
    result = await call(mcp, "pm_next", project="proj")
    assert "verified=True" in result
