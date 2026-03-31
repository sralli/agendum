"""Tests for board_format: BoardItem Markdown serialization round-trips."""

from __future__ import annotations

from datetime import UTC, datetime

from agendum.models import BoardItem, ProgressEntry, TaskPriority, TaskStatus, TaskType
from agendum.store.board_format import board_item_from_file, board_item_to_markdown


def _roundtrip(item: BoardItem, tmp_path) -> BoardItem:
    """Write item to markdown file, then parse it back."""
    path = tmp_path / f"{item.id}.md"
    path.write_text(board_item_to_markdown(item), encoding="utf-8")
    return board_item_from_file(path)


def test_roundtrip_minimal(tmp_path):
    item = BoardItem(id="item-001", project="test", title="Do the thing")
    result = _roundtrip(item, tmp_path)

    assert result.id == "item-001"
    assert result.project == "test"
    assert result.title == "Do the thing"
    assert result.status == TaskStatus.PENDING
    assert result.priority == TaskPriority.MEDIUM
    assert result.type == TaskType.DEV
    assert result.depends_on == []
    assert result.blocks == []
    assert result.tags == []
    assert result.notes == ""
    assert result.progress == []
    assert result.decisions == []


def test_roundtrip_full(tmp_path):
    now = datetime(2026, 3, 31, 12, 0, 0, tzinfo=UTC)
    item = BoardItem(
        id="item-042",
        project="myproj",
        title="Full item test",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        type=TaskType.RESEARCH,
        depends_on=["item-001", "item-002"],
        blocks=["item-099"],
        acceptance_criteria=["Tests pass", "Lint clean"],
        key_files=["src/foo.py", "tests/test_foo.py"],
        constraints=["No breaking changes"],
        tags=["v2", "store"],
        notes="This is a detailed note.\n\nWith multiple paragraphs.",
        created=now,
        updated=now,
        decisions=["Use Pydantic v2", "Keep snake_case keys"],
    )
    result = _roundtrip(item, tmp_path)

    assert result.id == "item-042"
    assert result.project == "myproj"
    assert result.title == "Full item test"
    assert result.status == TaskStatus.IN_PROGRESS
    assert result.priority == TaskPriority.HIGH
    assert result.type == TaskType.RESEARCH
    assert result.depends_on == ["item-001", "item-002"]
    assert result.blocks == ["item-099"]
    assert result.acceptance_criteria == ["Tests pass", "Lint clean"]
    assert result.key_files == ["src/foo.py", "tests/test_foo.py"]
    assert result.constraints == ["No breaking changes"]
    assert result.tags == ["v2", "store"]
    assert "detailed note" in result.notes
    assert "multiple paragraphs" in result.notes
    assert result.decisions == ["Use Pydantic v2", "Keep snake_case keys"]


def test_progress_roundtrip(tmp_path):
    ts = datetime(2026, 3, 31, 10, 30, 0, tzinfo=UTC)
    item = BoardItem(
        id="item-010",
        project="test",
        title="Progress test",
        progress=[
            ProgressEntry(timestamp=ts, agent="agent-1", message="Started work"),
            ProgressEntry(timestamp=ts, agent="agent-2", message="Finished review"),
        ],
    )
    result = _roundtrip(item, tmp_path)

    assert len(result.progress) == 2
    assert result.progress[0].agent == "agent-1"
    assert result.progress[0].message == "Started work"
    assert result.progress[1].agent == "agent-2"
    assert result.progress[1].message == "Finished review"


def test_decisions_roundtrip(tmp_path):
    item = BoardItem(
        id="item-020",
        project="test",
        title="Decisions test",
        decisions=["Decision A", "Decision B", "Decision C"],
    )
    result = _roundtrip(item, tmp_path)

    assert result.decisions == ["Decision A", "Decision B", "Decision C"]
