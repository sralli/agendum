"""Learnings store: global and project-scoped learnings stored as Markdown files."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from agendum.store import sanitize_name
from agendum.store.locking import atomic_write, get_lock, next_sequential_id


class LearningsStore:
    """File-based learnings storage.

    Global: .agendum/learnings/
    Project-scoped: .agendum/projects/<project>/learnings/
    """

    def __init__(self, root: Path):
        self.root = root
        self.learnings_dir = root / "learnings"

    def _ensure_dir(self) -> None:
        self.learnings_dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> str:
        return next_sequential_id(self.learnings_dir, "learning", "md")

    def _project_learnings_dir(self, project: str) -> Path:
        return self.root / "projects" / sanitize_name(project) / "learnings"

    def add_learning(
        self,
        content: str,
        tags: list[str] | None = None,
        source_project: str | None = None,
        project: str | None = None,
    ) -> str:
        """Add a new learning. If project is given, store project-scoped. Otherwise global."""
        if project:
            target_dir = self._project_learnings_dir(project)
        else:
            target_dir = self.learnings_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        learning_id = next_sequential_id(target_dir, "learning", "md")
        path = target_dir / f"{learning_id}.md"

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

    @staticmethod
    def _list_from_dir(directory: Path, tag: str | None = None) -> list[dict]:
        """List learnings from a given directory, optionally filtered by tag."""
        if not directory.exists():
            return []

        results = []
        for path in sorted(directory.glob("learning-*.md")):
            post = frontmatter.load(str(path))
            meta = dict(post.metadata)
            tags = meta.get("tags", [])
            if tag and tag not in tags:
                continue
            results.append(
                {
                    "id": meta.get("id", path.stem),
                    "tags": tags,
                    "source_project": meta.get("source_project"),
                    "created": meta.get("created"),
                    "content": post.content,
                }
            )
        return results

    def list_learnings(self, tag: str | None = None) -> list[dict]:
        """List all global learnings, optionally filtered by tag."""
        return self._list_from_dir(self.learnings_dir, tag)

    def search_learnings(self, query: str) -> list[dict]:
        """Search global learnings by content substring (case-insensitive)."""
        query_lower = query.lower()
        results = []
        for learning in self.list_learnings():
            content = learning.get("content", "")
            tags_str = " ".join(learning.get("tags", []))
            if query_lower in content.lower() or query_lower in tags_str.lower():
                results.append(learning)
        return results

    def list_project_learnings(self, project: str, tag: str | None = None) -> list[dict]:
        """List learnings for a specific project."""
        proj_dir = self._project_learnings_dir(project)
        return self._list_from_dir(proj_dir, tag)

    def search_project_learnings(self, project: str, query: str) -> list[dict]:
        """Search project-specific learnings by content substring (case-insensitive)."""
        query_lower = query.lower()
        results = []
        for learning in self.list_project_learnings(project):
            content = learning.get("content", "")
            tags_str = " ".join(learning.get("tags", []))
            if query_lower in content.lower() or query_lower in tags_str.lower():
                results.append(learning)
        return results
