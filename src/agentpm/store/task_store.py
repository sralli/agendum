"""Task store: read/write task Markdown files with YAML frontmatter."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from agentpm.models import ProgressEntry, Task, TaskStatus


def _tasks_dir(root: Path, project: str) -> Path:
    return root / "projects" / project / "tasks"


def _task_path(root: Path, project: str, task_id: str) -> Path:
    return _tasks_dir(root, project) / f"{task_id}.md"


def _next_task_id(root: Path, project: str) -> str:
    """Generate next sequential task ID like task-001, task-002."""
    tasks_dir = _tasks_dir(root, project)
    if not tasks_dir.exists():
        return "task-001"
    existing = sorted(tasks_dir.glob("task-*.md"))
    if not existing:
        return "task-001"
    last = existing[-1].stem  # e.g. "task-003"
    num = int(last.split("-")[1]) + 1
    return f"task-{num:03d}"


def _parse_progress(text: str) -> list[ProgressEntry]:
    """Parse progress log from markdown body."""
    entries = []
    pattern = re.compile(
        r"- \*\*\[(.+?)\] (.+?)\*\* [—–-] (.+)"
    )
    for match in pattern.finditer(text):
        try:
            ts = datetime.fromisoformat(match.group(1))
        except ValueError:
            ts = datetime.now(timezone.utc)
        entries.append(ProgressEntry(
            timestamp=ts,
            agent=match.group(2),
            message=match.group(3).strip(),
        ))
    return entries


def _extract_section(body: str, heading: str) -> str:
    """Extract content under a ## heading."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def _extract_list_items(text: str) -> list[str]:
    """Extract bullet list items from text."""
    return [
        line.lstrip("- ").strip()
        for line in text.splitlines()
        if line.strip().startswith("- ")
    ]


def task_from_file(path: Path) -> Task:
    """Parse a task Markdown file into a Task model."""
    post = frontmatter.load(str(path))
    meta = dict(post.metadata)
    body = post.content

    # Parse frontmatter fields
    depends_on = meta.get("dependsOn", [])
    if isinstance(depends_on, str):
        depends_on = [depends_on]

    blocks = meta.get("blocks", [])
    if isinstance(blocks, str):
        blocks = [blocks]

    acceptance = meta.get("acceptanceCriteria", [])
    if isinstance(acceptance, str):
        acceptance = [acceptance]

    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    # Parse body sections
    context = _extract_section(body, "Context")
    progress_text = _extract_section(body, "Progress")
    decisions_text = _extract_section(body, "Decisions")
    artifacts_text = _extract_section(body, "Artifacts")
    handoff = _extract_section(body, "Handoff")

    return Task(
        id=meta.get("id", path.stem),
        project=meta.get("project", ""),
        title=meta.get("title", "Untitled"),
        status=TaskStatus(meta.get("status", "pending")),
        priority=meta.get("priority", "medium"),
        type=meta.get("type", "dev"),
        category=meta.get("category"),
        assigned=meta.get("assigned"),
        created_by=meta.get("createdBy"),
        depends_on=depends_on,
        blocks=blocks,
        acceptance_criteria=acceptance,
        tags=tags,
        created=meta.get("created", datetime.now(timezone.utc)),
        updated=meta.get("updated", datetime.now(timezone.utc)),
        context=context,
        progress=_parse_progress(progress_text),
        decisions=_extract_list_items(decisions_text),
        artifacts=_extract_list_items(artifacts_text),
        handoff=handoff.lstrip("> ").strip(),
    )


def task_to_markdown(task: Task) -> str:
    """Serialize a Task model to Markdown with YAML frontmatter."""
    meta = {
        "id": task.id,
        "project": task.project,
        "title": task.title,
        "status": task.status.value,
        "priority": task.priority.value if hasattr(task.priority, "value") else task.priority,
        "type": task.type.value if hasattr(task.type, "value") else task.type,
        "assigned": task.assigned,
        "createdBy": task.created_by,
        "dependsOn": task.depends_on,
        "blocks": task.blocks,
        "acceptanceCriteria": task.acceptance_criteria,
        "tags": task.tags,
        "created": task.created.isoformat() if isinstance(task.created, datetime) else task.created,
        "updated": task.updated.isoformat() if isinstance(task.updated, datetime) else task.updated,
    }

    # Remove None values
    meta = {k: v for k, v in meta.items() if v is not None}

    # Build body
    sections = []

    sections.append("## Context")
    sections.append(task.context or "")
    sections.append("")

    sections.append("## Progress")
    if task.progress:
        for entry in task.progress:
            ts = entry.timestamp.strftime("%Y-%m-%dT%H:%MZ")
            sections.append(f"- **[{ts}] {entry.agent}** — {entry.message}")
    sections.append("")

    sections.append("## Decisions")
    for d in task.decisions:
        sections.append(f"- {d}")
    sections.append("")

    sections.append("## Artifacts")
    for a in task.artifacts:
        sections.append(f"- {a}")
    sections.append("")

    sections.append("## Handoff")
    if task.handoff:
        sections.append(f"> {task.handoff}")
    sections.append("")

    body = "\n".join(sections)
    post = frontmatter.Post(body, **meta)
    return frontmatter.dumps(post)


class TaskStore:
    """File-based task storage backed by .agentpm/ directory."""

    def __init__(self, root: Path):
        self.root = root

    def ensure_project(self, project: str) -> None:
        """Create project directory structure if needed."""
        _tasks_dir(self.root, project).mkdir(parents=True, exist_ok=True)

    def create_task(
        self,
        project: str,
        title: str,
        **kwargs,
    ) -> Task:
        """Create a new task and write to disk."""
        self.ensure_project(project)
        task_id = kwargs.pop("id", None) or _next_task_id(self.root, project)

        task = Task(
            id=task_id,
            project=project,
            title=title,
            **kwargs,
        )

        path = _task_path(self.root, project, task_id)
        path.write_text(task_to_markdown(task))
        return task

    def get_task(self, project: str, task_id: str) -> Task | None:
        """Read a task from disk."""
        path = _task_path(self.root, project, task_id)
        if not path.exists():
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
        """List tasks with optional filters."""
        tasks_dir = _tasks_dir(self.root, project)
        if not tasks_dir.exists():
            return []

        tasks = []
        for path in sorted(tasks_dir.glob("task-*.md")):
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

    def update_task(self, project: str, task_id: str, **updates) -> Task | None:
        """Update a task's fields and write back to disk."""
        task = self.get_task(project, task_id)
        if not task:
            return None

        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated = datetime.now(timezone.utc)
        path = _task_path(self.root, project, task_id)
        path.write_text(task_to_markdown(task))
        return task

    def add_progress(
        self, project: str, task_id: str, agent: str, message: str
    ) -> Task | None:
        """Append a progress entry to a task."""
        task = self.get_task(project, task_id)
        if not task:
            return None

        task.progress.append(ProgressEntry(
            timestamp=datetime.now(timezone.utc),
            agent=agent,
            message=message,
        ))
        task.updated = datetime.now(timezone.utc)

        path = _task_path(self.root, project, task_id)
        path.write_text(task_to_markdown(task))
        return task

    def delete_task(self, project: str, task_id: str) -> bool:
        """Delete a task file."""
        path = _task_path(self.root, project, task_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_projects(self) -> list[str]:
        """List all projects."""
        projects_dir = self.root / "projects"
        if not projects_dir.exists():
            return []
        return sorted(
            d.name for d in projects_dir.iterdir() if d.is_dir()
        )
