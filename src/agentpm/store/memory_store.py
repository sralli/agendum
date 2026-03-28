"""Memory store: read/write memory files in .agentpm/memory/."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class MemoryStore:
    """File-based memory storage."""

    SCOPES = ("project", "decisions", "patterns")

    def __init__(self, root: Path):
        self.root = root
        self.memory_dir = root / "memory"

    def ensure_dir(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _scope_path(self, scope: str) -> Path:
        return self.memory_dir / f"{scope}.md"

    def read(self, scope: str) -> str:
        """Read a memory scope file."""
        path = self._scope_path(scope)
        if path.exists():
            return path.read_text()
        return ""

    def write(self, scope: str, content: str) -> None:
        """Write/overwrite a memory scope file."""
        self.ensure_dir()
        path = self._scope_path(scope)
        path.write_text(content)

    def append(self, scope: str, entry: str, author: str | None = None) -> None:
        """Append an entry to a memory scope file."""
        self.ensure_dir()
        path = self._scope_path(scope)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        attribution = f" ({author})" if author else ""
        line = f"\n- [{ts}]{attribution} {entry}\n"

        with open(path, "a") as f:
            f.write(line)

    def search(self, query: str) -> dict[str, list[str]]:
        """Search across all memory scopes for matching lines."""
        results: dict[str, list[str]] = {}
        query_lower = query.lower()

        for scope in self.SCOPES:
            content = self.read(scope)
            if not content:
                continue
            matches = [
                line.strip()
                for line in content.splitlines()
                if query_lower in line.lower() and line.strip()
            ]
            if matches:
                results[scope] = matches

        return results

    def list_scopes(self) -> list[str]:
        """List available memory scopes."""
        if not self.memory_dir.exists():
            return []
        return [
            p.stem for p in self.memory_dir.glob("*.md")
        ]
