"""Board store: read/write board item Markdown files with YAML frontmatter."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agendum.models import BoardItem, ProgressEntry, TaskStatus
from agendum.store import sanitize_name
from agendum.store.board_format import board_item_from_file, board_item_to_markdown
from agendum.store.locking import atomic_create, atomic_write, get_lock, next_sequential_id

_MUTABLE_FIELDS = frozenset(
    {
        "status",
        "priority",
        "type",
        "depends_on",
        "blocks",
        "acceptance_criteria",
        "key_files",
        "constraints",
        "tags",
        "notes",
        "decisions",
        "verified",
    }
)


class BoardStore:
    """File-based board item storage backed by .agendum/ directory."""

    def __init__(self, root: Path):
        self.root = root

    # --- Path helpers ---

    def _board_dir(self, project: str) -> Path:
        return self.root / "projects" / sanitize_name(project) / "board"

    def _item_path(self, project: str, item_id: str) -> Path:
        return self._board_dir(project) / f"{sanitize_name(item_id)}.md"

    def _next_item_id(self, project: str) -> str:
        """Generate next sequential item ID."""
        board_dir = self._board_dir(project)
        return next_sequential_id(board_dir, "item", "md")

    def ensure_project(self, project: str) -> None:
        self._board_dir(project).mkdir(parents=True, exist_ok=True)

    # --- CRUD ---

    def create_item(self, project: str, title: str, **kwargs) -> BoardItem:
        """Create a new board item and write to disk. Uses atomic file creation."""
        self.ensure_project(project)
        item_id = kwargs.pop("id", None) or self._next_item_id(project)

        item = BoardItem(id=item_id, project=project, title=title, **kwargs)
        path = self._item_path(project, item_id)

        # Atomic creation: fails if file exists, retry with new ID
        for _attempt in range(20):
            try:
                atomic_create(path, board_item_to_markdown(item))
                return item
            except FileExistsError:
                item_id = self._next_item_id(project)
                item.id = item_id
                path = self._item_path(project, item_id)

        raise RuntimeError(f"Failed to create item after 20 retries in project '{project}'")

    def get_item(self, project: str, item_id: str) -> BoardItem | None:
        """Get a board item by ID. Done items stay in board/, no archive."""
        path = self._item_path(project, item_id)
        if not path.exists():
            return None
        return board_item_from_file(path)

    def list_items(
        self,
        project: str,
        status: TaskStatus | None = None,
        tag: str | None = None,
    ) -> list[BoardItem]:
        """List board items with optional filters."""
        board_dir = self._board_dir(project)
        if not board_dir.exists():
            return []

        items = []
        for path in sorted(board_dir.glob("item-*.md")):
            item = board_item_from_file(path)
            if status and item.status != status:
                continue
            if tag and tag not in item.tags:
                continue
            items.append(item)
        return items

    def update_item(self, project: str, item_id: str, **updates) -> BoardItem | None:
        """Update whitelisted fields and write back to disk (locked + atomic)."""
        path = self._item_path(project, item_id)
        with get_lock(path):
            if not path.exists():
                return None
            item = board_item_from_file(path)
            for key, value in updates.items():
                if key in _MUTABLE_FIELDS:
                    setattr(item, key, value)
            item.updated = datetime.now(UTC)
            atomic_write(path, board_item_to_markdown(item))
        return item

    def add_progress(self, project: str, item_id: str, agent: str, message: str) -> BoardItem | None:
        """Append a progress entry (locked + atomic to prevent concurrent data loss)."""
        path = self._item_path(project, item_id)
        with get_lock(path):
            if not path.exists():
                return None
            item = board_item_from_file(path)
            item.progress.append(
                ProgressEntry(
                    timestamp=datetime.now(UTC),
                    agent=agent,
                    message=message,
                )
            )
            item.updated = datetime.now(UTC)
            atomic_write(path, board_item_to_markdown(item))
        return item

    def delete_item(self, project: str, item_id: str) -> bool:
        """Delete a board item."""
        path = self._item_path(project, item_id)
        with get_lock(path):
            if not path.exists():
                return False
            path.unlink()
        Path(str(path) + ".lock").unlink(missing_ok=True)
        return True
