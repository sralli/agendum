"""Learnings store: global cross-project learnings stored as Markdown files."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from agendum.store.locking import atomic_write, get_lock, next_sequential_id


class LearningsStore:
    """File-based learnings storage in .agendum/learnings/."""

    def __init__(self, root: Path):
        self.root = root
        self.learnings_dir = root / "learnings"

    def _ensure_dir(self) -> None:
        self.learnings_dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> str:
        return next_sequential_id(self.learnings_dir, "learning", "md")

    def add_learning(self, content: str, tags: list[str] | None = None, source_project: str | None = None) -> str:
        """Add a new learning. Returns the learning ID."""
        self._ensure_dir()
        learning_id = self._next_id()
        path = self.learnings_dir / f"{learning_id}.md"

        meta: dict = {
            "id": learning_id,
            "tags": tags or [],
            "created": datetime.now(UTC).isoformat(),
        }
        if source_project:
            meta["source_project"] = source_project

        post = frontmatter.Post(content, **meta)
        text = frontmatter.dumps(post)

        with get_lock(path):
            atomic_write(path, text)

        return learning_id

    def list_learnings(self, tag: str | None = None) -> list[dict]:
        """List all learnings, optionally filtered by tag."""
        if not self.learnings_dir.exists():
            return []

        results = []
        for path in sorted(self.learnings_dir.glob("learning-*.md")):
            post = frontmatter.load(str(path))
            meta = dict(post.metadata)
            tags = meta.get("tags", [])
            if tag and tag not in tags:
                continue
            results.append({
                "id": meta.get("id", path.stem),
                "tags": tags,
                "source_project": meta.get("source_project"),
                "created": meta.get("created"),
                "content": post.content,
            })
        return results

    def search_learnings(self, query: str) -> list[dict]:
        """Search learnings by content substring (case-insensitive)."""
        query_lower = query.lower()
        results = []
        for learning in self.list_learnings():
            content = learning.get("content", "")
            tags_str = " ".join(learning.get("tags", []))
            if query_lower in content.lower() or query_lower in tags_str.lower():
                results.append(learning)
        return results
