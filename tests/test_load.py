"""Load tests — verify performance with 200 tasks."""
import time

from tests.conftest import call


async def _bulk_create(mcp, project: str, n: int) -> None:
    """Create n tasks in project (project must already exist)."""
    for i in range(n):
        await call(mcp, "pm_task_create", project=project, title=f"Load task {i}")


async def _setup_load_project(mcp, n: int = 200) -> str:
    """Initialize board, create project, bulk-create n tasks. Returns project name."""
    await call(mcp, "pm_board_init", name="loadboard")
    await call(mcp, "pm_project_create", name="load", description="load test project")
    await _bulk_create(mcp, "load", n)
    return "load"


async def test_list_200_tasks_under_500ms(mcp_server):
    mcp, _, _ = mcp_server
    await _setup_load_project(mcp, 200)
    start = time.perf_counter()
    result = await call(mcp, "pm_task_list", project="load")
    elapsed = time.perf_counter() - start
    print(f"\nlist_tasks(200): {elapsed*1000:.1f}ms")
    assert elapsed < 0.5, f"list_tasks took {elapsed:.3f}s, expected <0.5s"
    assert "task-" in result


async def test_get_task_under_100ms(mcp_server):
    mcp, _, _ = mcp_server
    await _setup_load_project(mcp, 200)
    start = time.perf_counter()
    result = await call(mcp, "pm_task_get", project="load", task_id="task-100")
    elapsed = time.perf_counter() - start
    print(f"\nget_task(task-100 of 200): {elapsed*1000:.1f}ms")
    assert elapsed < 0.1, f"get_task took {elapsed:.3f}s, expected <0.1s"
    assert "task-100" in result


async def test_list_with_status_filter_under_500ms(mcp_server):
    mcp, _, _ = mcp_server
    await _setup_load_project(mcp, 200)
    start = time.perf_counter()
    result = await call(mcp, "pm_task_list", project="load", status="pending")
    elapsed = time.perf_counter() - start
    print(f"\nlist_tasks(status=pending, 200 tasks): {elapsed*1000:.1f}ms")
    assert elapsed < 0.5, f"list_tasks with filter took {elapsed:.3f}s, expected <0.5s"
    assert "task-" in result
