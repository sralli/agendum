"""MCP layer tests: agent tools."""

from __future__ import annotations

from tests.conftest import call


async def _init(mcp) -> None:
    await call(mcp, "pm_board_init")
    await call(mcp, "pm_project_create", name="proj")


# --- pm_agent_register ---


async def test_agent_register_happy(mcp_server):
    mcp, _, agents = mcp_server
    result = await call(
        mcp,
        "pm_agent_register",
        agent_id="claude-1",
        agent_type="claude-code",
        capabilities="code,test",
        model="claude-sonnet-4-6",
    )
    assert "Registered agent 'claude-1'" in result
    assert "claude-1" in agents


async def test_agent_register_minimal(mcp_server):
    mcp, _, agents = mcp_server
    result = await call(mcp, "pm_agent_register", agent_id="simple-agent")
    assert "Registered" in result
    assert "simple-agent" in agents


# --- pm_agent_heartbeat ---


async def test_agent_heartbeat_happy(mcp_server):
    mcp, _, _ = mcp_server
    await call(mcp, "pm_agent_register", agent_id="a1")
    result = await call(mcp, "pm_agent_heartbeat", agent_id="a1")
    assert "Heartbeat recorded" in result


async def test_agent_heartbeat_unknown(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_agent_heartbeat", agent_id="ghost-agent")
    assert "not registered" in result


# --- pm_agent_list ---


async def test_agent_list_empty(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_agent_list")
    assert "No agents" in result


async def test_agent_list_shows_agents(mcp_server):
    mcp, _, _ = mcp_server
    await call(mcp, "pm_agent_register", agent_id="a1", agent_type="claude-code")
    await call(mcp, "pm_agent_register", agent_id="a2", agent_type="cursor")
    result = await call(mcp, "pm_agent_list")
    assert "a1" in result
    assert "a2" in result


# --- pm_agent_suggest ---


async def test_agent_suggest_dev_task(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Build feature", task_type="dev")
    result = await call(mcp, "pm_agent_suggest", project="proj", task_id="task-001")
    assert "code-complex" in result


async def test_agent_suggest_docs_task(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    await call(mcp, "pm_task_create", project="proj", title="Write docs", task_type="docs")
    result = await call(mcp, "pm_agent_suggest", project="proj", task_id="task-001")
    assert "docs" in result


async def test_agent_suggest_not_found(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    result = await call(mcp, "pm_agent_suggest", project="proj", task_id="task-999")
    assert "not found" in result


# --- pm_agent_register additional error/edge ---


async def test_agent_register_overwrites_existing(mcp_server):
    """pm_agent_register: re-registering same agent_id updates the record."""
    mcp, _, agents = mcp_server
    await call(mcp, "pm_agent_register", agent_id="dup-agent", agent_type="v1")
    result = await call(mcp, "pm_agent_register", agent_id="dup-agent", agent_type="v2")
    assert "Registered agent 'dup-agent'" in result
    assert agents["dup-agent"].type == "v2"


# --- pm_agent_suggest error path with invalid project ---


async def test_agent_suggest_invalid_project(mcp_server):
    """pm_agent_suggest: invalid project name (path traversal) returns Error."""
    mcp, _, _ = mcp_server
    await _init(mcp)
    result = await call(mcp, "pm_agent_suggest", project="../../nope", task_id="task-001")
    assert "Error" in result or "not found" in result.lower()


# --- pm_agent_list shows disconnected agents from disk ---


async def test_agent_list_shows_session_label(mcp_server):
    """pm_agent_list: registered agents show 'this session' label."""
    mcp, _, _ = mcp_server
    await call(mcp, "pm_agent_register", agent_id="session-agent", agent_type="claude")
    result = await call(mcp, "pm_agent_list")
    assert "this session" in result
