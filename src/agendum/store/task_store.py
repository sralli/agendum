"""Task store: read/write task Markdown files with YAML frontmatter."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from agendum.models import ProgressEntry, Task, TaskStatus
from agendum.store import sanitize_name
from agendum.store.locking import atomic_create, atomic_write, get_lock, next_sequential_id
from agendum.store.task_format import task_from_file, task_to_markdown

_MUTABLE_FIELDS = frozenset(
    {
        "status",
        "priority",
        "type",
        "category",
        "assigned",
        "depends_on",
        "blocks",
        "acceptance_criteria",
        "tags",
        "review_checklist",
        "test_requirements",
        "key_files",
        "constraints",
        "context",
        "decisions",
        "artifacts",
        "handoff",
        "structured_handoff",
        "agent_history",
    }
)


class TaskStore:
    """File-based task storage backed by .agendum/ directory."""

    def __init__(self, root: Path):
        self.root = root

    # --- Path helpers ---

    def _tasks_dir(self, project: str) -> Path:
        return self.root / "projects" / sanitize_name(project) / "tasks"

    def _task_path(self, project: str, task_id: str) -> Path:
        return self._tasks_dir(project) / f"{sanitize_name(task_id)}.md"

    def _next_task_id(self, project: str) -> str:
        """Generate next sequential task ID, scanning both active and archived tasks."""
        tasks_dir = self._tasks_dir(project)
        return next_sequential_id(tasks_dir, "task", "md", extra_dirs=[tasks_dir / "done"])

    def ensure_project(self, project: str) -> None:
        self._tasks_dir(project).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _filter_tasks(
        paths: Iterable[Path],
        status: TaskStatus | None,
        assigned: str | None,
        tag: str | None,
        task_type: str | None,
    ) -> list[Task]:
        tasks = []
        for path in paths:
            task = task_from_file(path)
            if status and task.status != status:
                continue
            if assigned and task.assigned != assigned:
                continue
            if tag and tag not in task.tags:
                continue
            if task_type and task.type.value != task_type:
                continue
            tasks.append(task)
        return tasks

    def create_task(self, project: str, title: str, **kwargs) -> Task:
        """Create a new task and write to disk. Uses atomic file creation."""
        self.ensure_project(project)
        task_id = kwargs.pop("id", None) or self._next_task_id(project)

        task = Task(id=task_id, project=project, title=title, **kwargs)
        path = self._task_path(project, task_id)

        # Atomic creation: fails if file exists, retry with new ID
        for _attempt in range(20):
            try:
                atomic_create(path, task_to_markdown(task))
                return task
            except FileExistsError:
                task_id = self._next_task_id(project)
                task.id = task_id
                path = self._task_path(project, task_id)

        raise RuntimeError(f"Failed to create task after 20 retries in project '{project}'")

    def get_task(self, project: str, task_id: str) -> Task | None:
        path = self._task_path(project, task_id)
        if not path.exists():
            # Check archive (tasks/done/) for completed/cancelled tasks
            archive_path = self._tasks_dir(project) / "done" / f"{sanitize_name(task_id)}.md"
            if archive_path.exists():
                return task_from_file(archive_path)
            return None
        return task_from_file(path)

    def list_tasks(
        self,
        project: str,
        status: TaskStatus | None = None,
        assigned: str | None = None,
        tag: str | None = None,
        task_type: str | None = None,
    ) -> list[Task]:
        tasks_dir = self._tasks_dir(project)
        if not tasks_dir.exists():
            return []

        return self._filter_tasks(sorted(tasks_dir.glob("task-*.md")), status, assigned, tag, task_type)

    def update_task(self, project: str, task_id: str, **updates) -> Task | None:
        """Update whitelisted fields and write back to disk (locked + atomic)."""
        path = self._task_path(project, task_id)
        with get_lock(path):
            if not path.exists():
                return None  # Don't update archived tasks via active path
            task = task_from_file(path)
            for key, value in updates.items():
                if key in _MUTABLE_FIELDS:
                    setattr(task, key, value)
            task.updated = datetime.now(UTC)
            atomic_write(path, task_to_markdown(task))
        return task

    def add_progress(self, project: str, task_id: str, agent: str, message: str) -> Task | None:
        """Append a progress entry (locked + atomic to prevent concurrent data loss)."""
        path = self._task_path(project, task_id)
        with get_lock(path):
            task = self.get_task(project, task_id)
            if not task:
                return None
            task.progress.append(
                ProgressEntry(
                    timestamp=datetime.now(UTC),
                    agent=agent,
                    message=message,
                )
            )
            task.updated = datetime.now(UTC)
            atomic_write(path, task_to_markdown(task))
        return task

    def delete_task(self, project: str, task_id: str) -> bool:
        path = self._task_path(project, task_id)
        with get_lock(path):
            if not path.exists():
                return False
            path.unlink()
        Path(str(path) + ".lock").unlink(missing_ok=True)
        return True

    def archive_task(self, project: str, task_id: str) -> Task:
        """Move a done/cancelled task from tasks/ to tasks/done/."""
        path = self._task_path(project, task_id)
        with get_lock(path):
            if not path.exists():
                raise FileNotFoundError(f"Task '{task_id}' not found in active tasks.")
            task = task_from_file(path)
            if task.status not in (TaskStatus.DONE, TaskStatus.CANCELLED):
                raise ValueError(
                    f"Cannot archive '{task_id}': status is {task.status.value}, must be done or cancelled."
                )
            archive_dir = self._tasks_dir(project) / "done"
            archive_dir.mkdir(parents=True, exist_ok=True)
            dest = archive_dir / f"{sanitize_name(task_id)}.md"
            content = path.read_text(encoding="utf-8")
            atomic_write(dest, content)
            path.unlink()
        # Clean up orphaned lock sidecar
        Path(str(path) + ".lock").unlink(missing_ok=True)
        return task

    def all_tasks(
        self,
        project: str,
        status: TaskStatus | None = None,
        assigned: str | None = None,
        tag: str | None = None,
        task_type: str | None = None,
    ) -> list[Task]:
        """Return active + archived tasks. Use for dependency resolution."""
        return self.list_tasks(
            project, status=status, assigned=assigned, tag=tag, task_type=task_type
        ) + self.list_archived_tasks(project, status=status, assigned=assigned, tag=tag, task_type=task_type)

    def list_archived_tasks(
        self,
        project: str,
        status: TaskStatus | None = None,
        assigned: str | None = None,
        tag: str | None = None,
        task_type: str | None = None,
    ) -> list[Task]:
        """List tasks in the archive (tasks/done/) with optional filters."""
        archive_dir = self._tasks_dir(project) / "done"
        if not archive_dir.exists():
            return []

        return self._filter_tasks(sorted(archive_dir.glob("task-*.md")), status, assigned, tag, task_type)
