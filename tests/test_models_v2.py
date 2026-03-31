"""Tests for v2 models: BoardItem and WorkPackage."""

from datetime import UTC, datetime

import pytest

from agendum.models import (
    BoardConfig,
    BoardItem,
    MemoryEntry,
    ProgressEntry,
    Project,
    TaskPriority,
    TaskStatus,
    TaskType,
    WorkPackage,
)


class TestBoardItem:
    def test_title_required(self):
        """title is a required field with no default."""
        with pytest.raises(ValueError, match="title"):
            BoardItem(id="t1", project="proj")

    def test_required_fields(self):
        item = BoardItem(id="t1", project="proj", title="Do stuff")
        assert item.title == "Do stuff"
        assert item.status == TaskStatus.PENDING
        assert item.type == TaskType.DEV
        assert item.priority == TaskPriority.MEDIUM

    def test_default_collections(self):
        item = BoardItem(id="t1", project="proj", title="X")
        assert item.depends_on == []
        assert item.blocks == []
        assert item.acceptance_criteria == []
        assert item.key_files == []
        assert item.constraints == []
        assert item.tags == []
        assert item.progress == []
        assert item.decisions == []
        assert item.notes == ""

    def test_timestamps(self):
        before = datetime.now(UTC)
        item = BoardItem(id="t1", project="proj", title="X")
        after = datetime.now(UTC)
        assert before <= item.created <= after
        assert before <= item.updated <= after

    def test_full_construction(self):
        item = BoardItem(
            id="t1",
            project="proj",
            title="Implement feature",
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.RESEARCH,
            priority=TaskPriority.HIGH,
            depends_on=["t0"],
            blocks=["t2"],
            acceptance_criteria=["Tests pass"],
            key_files=["src/main.py"],
            constraints=["No breaking changes"],
            tags=["backend"],
            notes="Some notes",
            decisions=["Use async"],
        )
        assert item.status == TaskStatus.IN_PROGRESS
        assert item.depends_on == ["t0"]
        assert item.blocks == ["t2"]
        assert item.decisions == ["Use async"]

    def test_progress_entries(self):
        entry = ProgressEntry(timestamp=datetime.now(UTC), agent="claude", message="Started work")
        item = BoardItem(id="t1", project="proj", title="X", progress=[entry])
        assert len(item.progress) == 1
        assert item.progress[0].agent == "claude"

    def test_serialization_roundtrip(self):
        item = BoardItem(id="t1", project="proj", title="Test", tags=["a", "b"])
        data = item.model_dump()
        restored = BoardItem.model_validate(data)
        assert restored.id == item.id
        assert restored.tags == ["a", "b"]


class TestWorkPackage:
    def test_minimal(self):
        item = BoardItem(id="t1", project="proj", title="Do thing")
        wp = WorkPackage(item=item)
        assert wp.item.id == "t1"
        assert wp.scope == ""
        assert wp.entry_criteria == []
        assert wp.exit_criteria == []
        assert wp.context == ""
        assert wp.constraints == []
        assert wp.key_files == []
        assert wp.dependency_context == ""
        assert wp.memory_context == ""
        assert wp.project_rules == ""
        assert wp.pointers == []

    def test_full_construction(self):
        item = BoardItem(id="t1", project="proj", title="Implement X")
        wp = WorkPackage(
            item=item,
            scope="Rewrite the models module",
            entry_criteria=["Models exist"],
            exit_criteria=["Tests pass", "Lint clean"],
            context="v2 rewrite",
            constraints=["No breaking changes"],
            key_files=["src/models.py"],
            dependency_context="t0 completed",
            memory_context="Use pydantic v2",
            project_rules="Line length 120",
            pointers=["See spec.md section 3"],
        )
        assert wp.scope == "Rewrite the models module"
        assert len(wp.exit_criteria) == 2
        assert wp.pointers == ["See spec.md section 3"]

    def test_serialization_roundtrip(self):
        item = BoardItem(id="t1", project="proj", title="Test")
        wp = WorkPackage(item=item, scope="test scope")
        data = wp.model_dump()
        restored = WorkPackage.model_validate(data)
        assert restored.item.id == "t1"
        assert restored.scope == "test scope"


class TestKeptModels:
    """Verify that models we're keeping still exist and work."""

    def test_task_status_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.DONE == "done"

    def test_task_priority_values(self):
        assert TaskPriority.CRITICAL == "critical"

    def test_task_type_values(self):
        assert TaskType.DEV == "dev"
        assert TaskType.RESEARCH == "research"

    def test_progress_entry(self):
        entry = ProgressEntry(timestamp=datetime.now(UTC), agent="test", message="msg")
        assert entry.agent == "test"

    def test_memory_entry(self):
        entry = MemoryEntry(key="k", scope="project", content="stuff")
        assert entry.key == "k"

    def test_board_config_no_agent_routing(self):
        """BoardConfig should not have agent_routing field in v2."""
        config = BoardConfig()
        assert not hasattr(config, "agent_routing") or "agent_routing" not in config.model_fields

    def test_project(self):
        proj = Project(name="test")
        assert proj.name == "test"
        assert proj.spec == ""


class TestCutModels:
    """Verify that cut models are no longer importable."""

    def test_no_agent(self):
        from agendum import models

        assert not hasattr(models, "Agent")

    def test_task_is_alias_for_board_item(self):
        from agendum import models

        # Task kept as alias for BoardItem (task_graph.py compatibility)
        assert models.Task is models.BoardItem

    def test_no_execution_plan(self):
        from agendum import models

        assert not hasattr(models, "ExecutionPlan")

    def test_no_context_packet(self):
        from agendum import models

        assert not hasattr(models, "ContextPacket")

    def test_no_board_status(self):
        from agendum import models

        assert not hasattr(models, "BoardStatus")

    def test_no_task_category(self):
        from agendum import models

        assert not hasattr(models, "TaskCategory")

    def test_no_model_routing(self):
        from agendum import models

        assert not hasattr(models, "ModelRouting")

    def test_no_project_policy(self):
        from agendum import models

        assert not hasattr(models, "ProjectPolicy")
