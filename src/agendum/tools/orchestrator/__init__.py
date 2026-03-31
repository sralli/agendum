"""Orchestrator tools package — structured planning, dispatch, review, and policy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agendum.tools.orchestrator.dispatch import register as register_dispatch
from agendum.tools.orchestrator.planning import register as register_planning
from agendum.tools.orchestrator.policy import register as register_policy
from agendum.tools.orchestrator.review import register as register_review

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from agendum.models import Agent


def register(mcp: FastMCP, stores: Any, agents: dict[str, Agent], enricher: Any = None) -> None:
    """Register all orchestrator tools on the MCP server."""
    register_planning(mcp, stores, agents)
    register_dispatch(mcp, stores, agents, enricher)
    register_review(mcp, stores, agents)
    register_policy(mcp, stores, agents)
