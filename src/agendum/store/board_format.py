"""Board item file parsing and serialization: Markdown <-> BoardItem model."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter

from agendum.models import BoardItem, ProgressEntry, TaskPriority, TaskStatus, TaskType

logger = logging.getLogger(__name__)

# --- Helpers ---


def _ensure_list(val: Any) -> list:
    """Coerce a value to a list (handles YAML scalars)."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def _safe_enum(enum_cls, value, default):
    """Safely convert a string to an enum, falling back to default."""
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError:
        return default


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


# --- File I/O ---


def board_item_from_file(path: Path) -> BoardItem:
    """Parse a board item Markdown file into a BoardItem model."""
    post = frontmatter.load(str(path))
    meta = dict(post.metadata)
    body = post.content

    # Parse body sections
    notes = _extract_section(body, "Notes")
    progress_text = _extract_section(body, "Progress")
    decisions_text = _extract_section(body, "Decisions")

    return BoardItem(
        id=meta.get("id", path.stem),
        project=meta.get("project", ""),
        title=meta.get("title", "Untitled"),
        status=_safe_enum(TaskStatus, meta.get("status"), TaskStatus.PENDING),
        priority=_safe_enum(TaskPriority, meta.get("priority"), TaskPriority.MEDIUM),
        type=_safe_enum(TaskType, meta.get("type"), TaskType.DEV),
        depends_on=_ensure_list(meta.get("depends_on")),
        blocks=_ensure_list(meta.get("blocks")),
        acceptance_criteria=_ensure_list(meta.get("acceptance_criteria")),
        key_files=_ensure_list(meta.get("key_files")),
        constraints=_ensure_list(meta.get("constraints")),
        tags=_ensure_list(meta.get("tags")),
        created=meta.get("created", datetime.now(UTC)),
        updated=meta.get("updated", datetime.now(UTC)),
        notes=notes,
        progress=_parse_progress(progress_text),
        decisions=_extract_list_items(decisions_text),
    )


def board_item_to_markdown(item: BoardItem) -> str:
    """Serialize a BoardItem model to Markdown with YAML frontmatter."""
    meta: dict[str, Any] = {
        "id": item.id,
        "project": item.project,
        "title": item.title,
        "status": item.status.value,
        "priority": item.priority.value,
        "type": item.type.value,
        "depends_on": item.depends_on,
        "blocks": item.blocks,
        "acceptance_criteria": item.acceptance_criteria,
        "key_files": item.key_files,
        "constraints": item.constraints,
        "tags": item.tags,
        "created": item.created.isoformat() if isinstance(item.created, datetime) else item.created,
        "updated": item.updated.isoformat() if isinstance(item.updated, datetime) else item.updated,
    }

    # Remove None values and empty lists
    meta = {k: v for k, v in meta.items() if v is not None}

    # Build body
    sections = []

    sections.append("## Notes")
    sections.append(item.notes or "")
    sections.append("")

    sections.append("## Progress")
    for entry in item.progress:
        sections.append(f"- **[{entry.timestamp.isoformat()}] {entry.agent}** — {entry.message}")
    sections.append("")

    sections.append("## Decisions")
    for d in item.decisions:
        sections.append(f"- {d}")
    sections.append("")

    body = "\n".join(sections)
    post = frontmatter.Post(body, **meta)
    return frontmatter.dumps(post)
