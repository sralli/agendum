"""MCP layer tests: memory tools."""

from __future__ import annotations

import pytest

from tests.conftest import call


async def _init(mcp) -> None:
    await call(mcp, "pm_board_init")


# --- pm_memory_write + pm_memory_read ---

@pytest.mark.asyncio
async def test_memory_write_and_read(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    await call(mcp, "pm_memory_write", scope="project", content="# Project Notes\n\nFoo bar.")
    result = await call(mcp, "pm_memory_read", scope="project")
    assert "Foo bar" in result


@pytest.mark.asyncio
async def test_memory_read_empty(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    result = await call(mcp, "pm_memory_read", scope="project")
    assert "is empty" in result


@pytest.mark.asyncio
async def test_memory_read_all_scopes(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    for scope in ("project", "decisions", "patterns"):
        await call(mcp, "pm_memory_write", scope=scope, content=f"content for {scope}")
        result = await call(mcp, "pm_memory_read", scope=scope)
        assert f"content for {scope}" in result


@pytest.mark.asyncio
async def test_memory_read_invalid_scope(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_memory_read", scope="bogus")
    assert "Error:" in result


@pytest.mark.asyncio
async def test_memory_write_invalid_scope(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_memory_write", scope="bogus", content="nope")
    assert "Error:" in result


# --- pm_memory_append ---

@pytest.mark.asyncio
async def test_memory_append_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    result = await call(mcp, "pm_memory_append", scope="decisions",
                        entry="Use filelock for safety", author="agent-1")
    assert "Appended" in result
    content = await call(mcp, "pm_memory_read", scope="decisions")
    assert "Use filelock for safety" in content
    assert "agent-1" in content


@pytest.mark.asyncio
async def test_memory_append_multiple(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    await call(mcp, "pm_memory_append", scope="patterns", entry="Entry 1")
    await call(mcp, "pm_memory_append", scope="patterns", entry="Entry 2")
    content = await call(mcp, "pm_memory_read", scope="patterns")
    assert "Entry 1" in content
    assert "Entry 2" in content


@pytest.mark.asyncio
async def test_memory_append_invalid_scope(mcp_server):
    mcp, _, _ = mcp_server
    result = await call(mcp, "pm_memory_append", scope="bogus", entry="nope")
    assert "Error:" in result


# --- pm_memory_search ---

@pytest.mark.asyncio
async def test_memory_search_happy(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    await call(mcp, "pm_memory_write", scope="project", content="We chose filelock for safety.")
    await call(mcp, "pm_memory_write", scope="decisions", content="filelock over fcntl.")
    result = await call(mcp, "pm_memory_search", query="filelock")
    assert "filelock" in result
    assert "Search results" in result


@pytest.mark.asyncio
async def test_memory_search_no_matches(mcp_server):
    mcp, _, _ = mcp_server
    await _init(mcp)
    result = await call(mcp, "pm_memory_search", query="xyzzy_not_found")
    assert "No matches" in result
