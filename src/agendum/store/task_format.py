"""Task file parsing and serialization: Markdown ↔ Task model."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import frontmatter
import yaml

from agendum.models import AgentHandoffRecord, ProgressEntry, Task, TaskPriority, TaskStatus, TaskType

logger = logging.getLogger(__name__)

# --- Helpers ---


def _ensure_list(val) -> list:
    """Coerce a value to a list (handles YAML scalars)."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


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


def _load_yaml_block(text: str):
    """Extract and parse a fenced YAML block from markdown text."""
    match = _YAML_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except Exception:
        logger.warning("Failed to parse YAML block")
        return None


def _parse_structured_handoff(text: str) -> AgentHandoffRecord | None:
    """Try to parse a fenced YAML block from handoff text into AgentHandoffRecord."""
    data = _load_yaml_block(text)
    if not isinstance(data, dict):
        return None
    try:
        return AgentHandoffRecord.model_validate(data)
    except Exception:
        logger.warning("Failed to validate structured handoff")
        return None


def _parse_agent_history(text: str) -> list[AgentHandoffRecord]:
    """Parse agent history section (fenced YAML list) into AgentHandoffRecord list."""
    data = _load_yaml_block(text)
    if not isinstance(data, list):
        return []
    try:
        return [AgentHandoffRecord.model_validate(item) for item in data if isinstance(item, dict)]
    except Exception:
        logger.warning("Failed to validate agent history")
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
        review_checklist=_ensure_list(meta.get("reviewChecklist")),
        test_requirements=_ensure_list(meta.get("testRequirements")),
        key_files=_ensure_list(meta.get("keyFiles")),
        constraints=_ensure_list(meta.get("constraints")),
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
        "reviewChecklist": task.review_checklist,
        "testRequirements": task.test_requirements,
        "keyFiles": task.key_files,
        "constraints": task.constraints,
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
