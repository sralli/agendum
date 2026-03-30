"""Tests for task store: file I/O, parsing, CRUD."""

import tempfile
from pathlib import Path

import pytest

from agendum.models import TaskStatus
from agendum.store.task_store import TaskStore


def _tmp_root():
    return Path(tempfile.mkdtemp()) / ".agendum"


class TestTaskStore:
    def test_create_task(self):
        store = TaskStore(_tmp_root())
        task = store.create_task("demo", "Setup project", priority="high")
        assert task.id == "task-001"
        assert task.title == "Setup project"
        assert task.status == TaskStatus.PENDING
        assert task.project == "demo"

    def test_sequential_ids(self):
        store = TaskStore(_tmp_root())
        t1 = store.create_task("demo", "First")
        t2 = store.create_task("demo", "Second")
        t3 = store.create_task("demo", "Third")
        assert t1.id == "task-001"
        assert t2.id == "task-002"
        assert t3.id == "task-003"

    def test_get_task(self):
        store = TaskStore(_tmp_root())
        created = store.create_task("demo", "Test", priority="critical", type="docs")
        fetched = store.get_task("demo", created.id)
        assert fetched is not None
        assert fetched.title == "Test"
        assert fetched.priority.value == "critical"
        assert fetched.type.value == "docs"

    def test_get_nonexistent(self):
        store = TaskStore(_tmp_root())
        assert store.get_task("demo", "task-999") is None

    def test_list_tasks(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "A")
        store.create_task("demo", "B")
        store.create_task("other", "C")

        demo_tasks = store.list_tasks("demo")
        assert len(demo_tasks) == 2

        other_tasks = store.list_tasks("other")
        assert len(other_tasks) == 1

    def test_list_with_status_filter(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "A")
        store.create_task("demo", "B")
        store.update_task("demo", "task-001", status=TaskStatus.IN_PROGRESS)

        pending = store.list_tasks("demo", status=TaskStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].id == "task-002"

    def test_update_task(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "Original")
        updated = store.update_task("demo", "task-001", status=TaskStatus.IN_PROGRESS, assigned="claude")
        assert updated is not None
        assert updated.status == TaskStatus.IN_PROGRESS
        assert updated.assigned == "claude"

        # Verify persisted
        fetched = store.get_task("demo", "task-001")
        assert fetched.status == TaskStatus.IN_PROGRESS

    def test_add_progress(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "Test")
        store.add_progress("demo", "task-001", "claude", "Started work")
        store.add_progress("demo", "task-001", "claude", "Halfway done")

        task = store.get_task("demo", "task-001")
        assert len(task.progress) == 2
        assert task.progress[0].agent == "claude"
        assert task.progress[0].message == "Started work"

    def test_delete_task(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "To delete")
        assert store.delete_task("demo", "task-001")
        assert store.get_task("demo", "task-001") is None
        assert not store.delete_task("demo", "task-001")

    def test_multiple_projects(self):
        root = _tmp_root()
        store = TaskStore(root)
        store.create_task("alpha", "A")
        store.create_task("beta", "B")
        # Verify both project directories were created
        projects_dir = root / "projects"
        projects = sorted(d.name for d in projects_dir.iterdir() if d.is_dir())
        assert "alpha" in projects
        assert "beta" in projects

    def test_dependencies_in_frontmatter(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "First")
        store.create_task("demo", "Second", depends_on=["task-001"], blocks=["task-003"])

        task = store.get_task("demo", "task-002")
        assert task.depends_on == ["task-001"]
        assert task.blocks == ["task-003"]

    def test_acceptance_criteria(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "Auth", acceptance_criteria=["Login works", "Logout works"])

        task = store.get_task("demo", "task-001")
        assert len(task.acceptance_criteria) == 2
        assert "Login works" in task.acceptance_criteria


class TestArchive:
    def test_archive_done_task(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "Done task")
        store.update_task("demo", "task-001", status=TaskStatus.DONE)
        task = store.archive_task("demo", "task-001")
        assert task.title == "Done task"
        # No longer in active list
        assert len(store.list_tasks("demo")) == 0
        # Still accessible via get_task (falls back to archive)
        assert store.get_task("demo", "task-001") is not None

    def test_archive_cancelled_task(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "Cancelled task")
        store.update_task("demo", "task-001", status=TaskStatus.CANCELLED)
        store.archive_task("demo", "task-001")
        assert len(store.list_tasks("demo")) == 0
        assert store.get_task("demo", "task-001") is not None

    def test_archive_pending_task_fails(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "Pending task")
        with pytest.raises(ValueError, match="pending"):
            store.archive_task("demo", "task-001")

    def test_archive_nonexistent_task_fails(self):
        store = TaskStore(_tmp_root())
        store.ensure_project("demo")
        with pytest.raises(FileNotFoundError):
            store.archive_task("demo", "task-999")

    def test_unarchive_task(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "To archive")
        store.update_task("demo", "task-001", status=TaskStatus.DONE)
        store.archive_task("demo", "task-001")
        assert len(store.list_tasks("demo")) == 0

        task = store.unarchive_task("demo", "task-001")
        assert task.title == "To archive"
        assert len(store.list_tasks("demo")) == 1

    def test_unarchive_nonexistent_fails(self):
        store = TaskStore(_tmp_root())
        store.ensure_project("demo")
        with pytest.raises(FileNotFoundError):
            store.unarchive_task("demo", "task-999")

    def test_list_archived_tasks(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "A")
        store.create_task("demo", "B")
        store.create_task("demo", "C")
        store.update_task("demo", "task-001", status=TaskStatus.DONE)
        store.update_task("demo", "task-002", status=TaskStatus.CANCELLED)
        store.archive_task("demo", "task-001")
        store.archive_task("demo", "task-002")

        archived = store.list_archived_tasks("demo")
        assert len(archived) == 2
        assert {t.id for t in archived} == {"task-001", "task-002"}

        # Active list only has task-003
        active = store.list_tasks("demo")
        assert len(active) == 1
        assert active[0].id == "task-003"

    def test_list_archived_empty(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "Active")
        assert store.list_archived_tasks("demo") == []

    def test_list_archived_with_filter(self):
        store = TaskStore(_tmp_root())
        store.create_task("demo", "Done task")
        store.create_task("demo", "Cancelled task")
        store.update_task("demo", "task-001", status=TaskStatus.DONE)
        store.update_task("demo", "task-002", status=TaskStatus.CANCELLED)
        store.archive_task("demo", "task-001")
        store.archive_task("demo", "task-002")

        done_only = store.list_archived_tasks("demo", status=TaskStatus.DONE)
        assert len(done_only) == 1
        assert done_only[0].id == "task-001"


class TestRoundTrip:
    def test_new_metadata_fields_roundtrip(self):
        store = TaskStore(_tmp_root())
        original = store.create_task(
            "demo",
            "Metadata test",
            review_checklist=["Check A", "Check B"],
            test_requirements=["test_foo passes", "test_bar passes"],
            key_files=["src/main.py", "tests/test_main.py"],
            constraints=["Do not modify config.py"],
        )
        recovered = store.get_task("demo", original.id)
        assert recovered.review_checklist == ["Check A", "Check B"]
        assert recovered.test_requirements == ["test_foo passes", "test_bar passes"]
        assert recovered.key_files == ["src/main.py", "tests/test_main.py"]
        assert recovered.constraints == ["Do not modify config.py"]

    def test_markdown_roundtrip(self):
        """Task -> Markdown -> Task should preserve all fields."""
        store = TaskStore(_tmp_root())
        original = store.create_task(
            "demo",
            "Roundtrip test",
            priority="high",
            type="dev",
            depends_on=["task-000"],
            blocks=["task-999"],
            acceptance_criteria=["It works", "It's fast"],
            tags=["auth", "backend"],
        )
        store.add_progress("demo", original.id, "agent-1", "Started")
        store.update_task("demo", original.id, handoff="Pick up from here")

        recovered = store.get_task("demo", original.id)
        assert recovered.title == original.title
        assert recovered.priority.value == "high"
        assert recovered.depends_on == ["task-000"]
        assert recovered.blocks == ["task-999"]
        assert len(recovered.acceptance_criteria) == 2
        assert len(recovered.progress) == 1
        assert recovered.handoff == "Pick up from here"
