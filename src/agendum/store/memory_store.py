"""Memory store: read/write memory files in .agendum/memory/."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agendum.store.locking import atomic_write, get_lock


class MemoryStore:
    """File-based memory storage."""

    SCOPES = ("project", "decisions", "patterns")

    def __init__(self, root: Path):
        self.root = root
        self.memory_dir = root / "memory"

    def _validate_scope(self, scope: str) -> None:
        """Validate scope against allowlist to prevent path traversal."""
        if scope not in self.SCOPES:
            raise ValueError(f"Invalid memory scope: {scope!r}. Must be one of: {', '.join(self.SCOPES)}")

    def ensure_dir(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _scope_path(self, scope: str) -> Path:
        self._validate_scope(scope)
        return self.memory_dir / f"{scope}.md"

    def read(self, scope: str) -> str:
        """Read a memory scope file."""
        path = self._scope_path(scope)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write(self, scope: str, content: str) -> None:
        """Write/overwrite a memory scope file (locked + atomic)."""
        self.ensure_dir()
        path = self._scope_path(scope)
        with get_lock(path):
            atomic_write(path, content)

    def append(self, scope: str, entry: str, author: str | None = None) -> None:
        """Append an entry to a memory scope file (locked + atomic)."""
        self.ensure_dir()
        path = self._scope_path(scope)

        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")
        attribution = f" ({author})" if author else ""
        line = f"\n- [{ts}]{attribution} {entry}\n"

        with get_lock(path):
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            atomic_write(path, existing + line)

    def search(self, query: str) -> dict[str, list[str]]:
        """Search across all memory scopes for matching lines."""
        results: dict[str, list[str]] = {}
        query_lower = query.lower()

        for scope in self.SCOPES:
            content = self.read(scope)
            if not content:
                continue
            matches = [line.strip() for line in content.splitlines() if query_lower in line.lower() and line.strip()]
            if matches:
                results[scope] = matches

        return results

    def list_scopes(self) -> list[str]:
        """List available memory scopes."""
        if not self.memory_dir.exists():
            return []
        return [p.stem for p in self.memory_dir.glob("*.md") if p.stem in self.SCOPES]
