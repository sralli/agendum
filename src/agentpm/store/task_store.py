"""Task store: read/write task Markdown files with YAML frontmatter."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml
import frontmatter

from agentpm.models import AgentHandoffRecord, ProgressEntry, Task, TaskPriority, TaskStatus, TaskType
from agentpm.store import sanitize_name
from agentpm.store.locking import atomic_write, get_lock

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
        "context",
        "decisions",
        "artifacts",
        "handoff",
        "structured_handoff",
        "agent_history",
    }
)


# --- Helpers ---


def _ensure_list(val) -> list:
    """Coerce a value to a list (handles YAML scalars)."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def _tasks_dir(root: Path, project: str) -> Path:
    return root / "projects" / sanitize_name(project) / "tasks"


def _task_path(root: Path, project: str, task_id: str) -> Path:
    return _tasks_dir(root, project) / f"{sanitize_name(task_id)}.md"


def _next_task_id(root: Path, project: str) -> str:
    """Generate next sequential task ID like task-001, task-002."""
    tasks_dir = _tasks_dir(root, project)
    if not tasks_dir.exists():
        return "task-001"

    max_num = 0
    for path in tasks_dir.glob("task-*.md"):
        parts = path.stem.split("-", 1)
        if len(parts) == 2:
            try:
                max_num = max(max_num, int(parts[1]))
            except ValueError:
                continue

    return f"task-{max_num + 1:03d}"


def _parse_progress(text: str) -> list[ProgressEntry]:
    """Parse progress log from markdown body."""
    entries = []
    pattern = re.compile(r"- \*\*\[(.+?)\] (.+?)\*\* [—–-] (.+)")
    for match in pattern.finditer(text):
        try:
            ts = datetime.fromisoformat(match.group(1))
        except ValueError:
            ts = datetime.now(UTC)
        entries.append(
            ProgressEntry(
                timestamp=ts,
                agent=match.group(2),
                message=match.group(3).strip(),
            )
        )
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
    """Extract bullet list items from text (exact '- ' prefix removal)."""
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _strip_blockquote(text: str) -> str:
    """Strip markdown blockquote prefix."""
    if text.startswith("> "):
        return text[2:].strip()
    if text.startswith(">"):
        return text[1:].strip()
    return text.strip()


_YAML_BLOCK_RE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)


def _parse_structured_handoff(text: str) -> AgentHandoffRecord | None:
    """Try to parse a fenced YAML block from handoff text into AgentHandoffRecord."""
    match = _YAML_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
        if not isinstance(data, dict):
            return None
        return AgentHandoffRecord.model_validate(data)
    except Exception:
        return None


def _parse_agent_history(text: str) -> list[AgentHandoffRecord]:
    """Parse agent history section (fenced YAML list) into AgentHandoffRecord list."""
    match = _YAML_BLOCK_RE.search(text)
    if not match:
        return []
    try:
        data = yaml.safe_load(match.group(1))
        if not isinstance(data, list):
            return []
        return [AgentHandoffRecord.model_validate(item) for item in data if isinstance(item, dict)]
    except Exception:
        return []


def _handoff_record_to_yaml(record: AgentHandoffRecord) -> str:
    """Serialize an AgentHandoffRecord to a YAML dict string."""
    d = record.model_dump(exclude_none=True)
    # Convert datetime to ISO string for YAML
    if "timestamp" in d and hasattr(d["timestamp"], "isoformat"):
        d["timestamp"] = d["timestamp"].isoformat()
    return yaml.dump(d, default_flow_style=False, sort_keys=False).rstrip()


def _safe_enum(enum_cls, value, default):
    """Safely convert a string to an enum, falling back to default."""
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError:
        return default


# --- File I/O ---


def task_from_file(path: Path) -> Task:
    """Parse a task Markdown file into a Task model."""
    post = frontmatter.load(str(path))
    meta = dict(post.metadata)
    body = post.content

    # Parse body sections
    context = _extract_section(body, "Context")
    progress_text = _extract_section(body, "Progress")
    decisions_text = _extract_section(body, "Decisions")
    artifacts_text = _extract_section(body, "Artifacts")
    handoff_raw = _extract_section(body, "Handoff")
    history_raw = _extract_section(body, "Agent History")

    # Parse structured handoff if present (fenced YAML block); else use legacy free text
    structured = _parse_structured_handoff(handoff_raw)
    legacy_handoff = "" if structured else _strip_blockquote(handoff_raw)

    return Task(
        id=meta.get("id", path.stem),
        project=meta.get("project", ""),
        title=meta.get("title", "Untitled"),
        status=_safe_enum(TaskStatus, meta.get("status"), TaskStatus.PENDING),
        priority=_safe_enum(TaskPriority, meta.get("priority"), TaskPriority.MEDIUM),
        type=_safe_enum(TaskType, meta.get("type"), TaskType.DEV),
        category=meta.get("category"),
        assigned=meta.get("assigned"),
        created_by=meta.get("createdBy"),
        depends_on=_ensure_list(meta.get("dependsOn")),
        blocks=_ensure_list(meta.get("blocks")),
        acceptance_criteria=_ensure_list(meta.get("acceptanceCriteria")),
        tags=_ensure_list(meta.get("tags")),
        created=meta.get("created", datetime.now(UTC)),
        updated=meta.get("updated", datetime.now(UTC)),
        context=context,
        progress=_parse_progress(progress_text),
        decisions=_extract_list_items(decisions_text),
        artifacts=_extract_list_items(artifacts_text),
        handoff=legacy_handoff,
        structured_handoff=structured,
        agent_history=_parse_agent_history(history_raw),
    )


def task_to_markdown(task: Task) -> str:
    """Serialize a Task model to Markdown with YAML frontmatter."""
    meta = {
        "id": task.id,
        "project": task.project,
        "title": task.title,
        "status": task.status.value,
        "priority": task.priority.value,
        "type": task.type.value,
        "category": task.category.value if task.category else None,
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
    for entry in task.progress:
        sections.append(f"- **[{entry.timestamp.isoformat()}] {entry.agent}** — {entry.message}")
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
    if task.structured_handoff:
        sections.append("```yaml")
        sections.append(_handoff_record_to_yaml(task.structured_handoff))
        sections.append("```")
    elif task.handoff:
        sections.append(f"> {task.handoff}")
    sections.append("")

    if task.agent_history:
        sections.append("## Agent History")
        history_data = []
        for rec in task.agent_history:
            d = rec.model_dump(exclude_none=True)
            if "timestamp" in d and hasattr(d["timestamp"], "isoformat"):
                d["timestamp"] = d["timestamp"].isoformat()
            history_data.append(d)
        sections.append("```yaml")
        sections.append(yaml.dump(history_data, default_flow_style=False, sort_keys=False).rstrip())
        sections.append("```")
        sections.append("")

    body = "\n".join(sections)
    post = frontmatter.Post(body, **meta)
    return frontmatter.dumps(post)


class TaskStore:
    """File-based task storage backed by .agentpm/ directory."""

    def __init__(self, root: Path):
        self.root = root

    def ensure_project(self, project: str) -> None:
        _tasks_dir(self.root, project).mkdir(parents=True, exist_ok=True)

    def create_task(self, project: str, title: str, **kwargs) -> Task:
        """Create a new task and write to disk. Uses atomic file creation."""
        self.ensure_project(project)
        task_id = kwargs.pop("id", None) or _next_task_id(self.root, project)

        task = Task(id=task_id, project=project, title=title, **kwargs)
        path = _task_path(self.root, project, task_id)

        # Atomic write: O_CREAT|O_EXCL fails if file exists, retry with new ID
        for _attempt in range(20):
            try:
                fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, task_to_markdown(task).encode())
                finally:
                    os.close(fd)
                return task
            except FileExistsError:
                task_id = _next_task_id(self.root, project)
                task.id = task_id
                path = _task_path(self.root, project, task_id)

        raise RuntimeError(f"Failed to create task after 20 retries in project '{project}'")

    def get_task(self, project: str, task_id: str) -> Task | None:
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
        """Update whitelisted fields and write back to disk (locked + atomic)."""
        path = _task_path(self.root, project, task_id)
        with get_lock(path):
            task = self.get_task(project, task_id)
            if not task:
                return None
            for key, value in updates.items():
                if key in _MUTABLE_FIELDS:
                    setattr(task, key, value)
            task.updated = datetime.now(UTC)
            atomic_write(path, task_to_markdown(task))
        return task

    def add_progress(self, project: str, task_id: str, agent: str, message: str) -> Task | None:
        """Append a progress entry (locked + atomic to prevent concurrent data loss)."""
        path = _task_path(self.root, project, task_id)
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
        path = _task_path(self.root, project, task_id)
        if path.exists():
            path.unlink()
            return True
        return False
