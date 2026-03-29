"""Memory tools: read, write, append, search across scoped memory files."""

from __future__ import annotations


def register(mcp, stores, agents):
    """Register memory tools on the MCP server."""

    @mcp.tool()
    def pm_memory_read(scope: str = "project") -> str:
        """Read a memory scope. Valid scopes: project, decisions, patterns.

        - project: shared learnings about the codebase and architecture
        - decisions: key decisions with rationale (why we chose X over Y)
        - patterns: discovered conventions and coding patterns
        """
        try:
            content = stores.memory.read(scope)
        except ValueError as e:
            return f"Error: {e}"
        if not content:
            return f"Memory scope '{scope}' is empty."
        return f"# Memory: {scope}\n\n{content}"

    @mcp.tool()
    def pm_memory_write(scope: str, content: str) -> str:
        """Overwrite a memory scope with new content. Valid scopes: project, decisions, patterns.

        Use pm_memory_append to add entries without overwriting. Use this only
        when you want to replace the entire scope content (e.g., restructuring).
        """
        try:
            stores.memory.write(scope, content)
        except ValueError as e:
            return f"Error: {e}"
        return f"Memory '{scope}' updated."

    @mcp.tool()
    def pm_memory_append(scope: str, entry: str, author: str = "unknown") -> str:
        """Append a timestamped entry to a memory scope. Valid scopes: project, decisions, patterns.

        Use this to record learnings, decisions, or patterns as you work.
        Each entry is timestamped and attributed to the author.
        """
        try:
            stores.memory.append(scope, entry, author)
        except ValueError as e:
            return f"Error: {e}"
        return f"Appended to memory '{scope}'."

    @mcp.tool()
    def pm_memory_search(query: str) -> str:
        """Search across all memory scopes for lines matching the query string."""
        results = stores.memory.search(query)
        if not results:
            return f"No matches found for '{query}'."

        lines = [f"Search results for '{query}':"]
        for scope, matches in results.items():
            lines.append(f"\n## {scope}")
            for m in matches[:5]:
                lines.append(f"  {m}")
        return "\n".join(lines)
