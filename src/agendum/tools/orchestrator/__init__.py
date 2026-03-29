"""Orchestrator tools package — structured planning, dispatch, review, and policy."""

from agendum.tools.orchestrator.dispatch import register as register_dispatch
from agendum.tools.orchestrator.planning import register as register_planning
from agendum.tools.orchestrator.policy import register as register_policy
from agendum.tools.orchestrator.review import register as register_review


def register(mcp, stores, agents, enricher=None):
    """Register all orchestrator tools on the MCP server."""
    register_planning(mcp, stores, agents)
    register_dispatch(mcp, stores, agents, enricher)
    register_review(mcp, stores, agents)
    register_policy(mcp, stores, agents)
