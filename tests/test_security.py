"""Tests for path traversal prevention and input validation."""

import pytest

from agendum.store import sanitize_name
from agendum.store.memory_store import MemoryStore
from agendum.store.project_store import ProjectStore
from agendum.store.task_store import TaskStore


class TestSanitizeName:
    def test_valid_names(self):
        assert sanitize_name("my-project") == "my-project"
        assert sanitize_name("task-001") == "task-001"
        assert sanitize_name("webapp_v2") == "webapp_v2"

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError):
            sanitize_name("../../etc")

    def test_rejects_forward_slash(self):
        with pytest.raises(ValueError):
            sanitize_name("path/to/evil")

    def test_rejects_backslash(self):
        with pytest.raises(ValueError):
            sanitize_name("path\\to\\evil")

    def test_rejects_null_byte(self):
        with pytest.raises(ValueError):
            sanitize_name("evil\x00name")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            sanitize_name("")

    def test_strips_leading_dot(self):
        assert sanitize_name(".hidden") == "hidden"

    def test_rejects_only_dots(self):
        with pytest.raises(ValueError):
            sanitize_name("...")


class TestTaskStorePathTraversal:
    def test_create_rejects_traversal_project(self, tmp_root):
        store = TaskStore(tmp_root)
        with pytest.raises(ValueError):
            store.create_task("../../etc", "evil task")

    def test_get_rejects_traversal_task_id(self, tmp_root):
        store = TaskStore(tmp_root)
        with pytest.raises(ValueError):
            store.get_task("demo", "../../etc/passwd")

    def test_list_rejects_traversal(self, tmp_root):
        store = TaskStore(tmp_root)
        with pytest.raises(ValueError):
            store.list_tasks("../../../")


class TestMemoryStoreValidation:
    def test_rejects_invalid_scope(self, tmp_root):
        store = MemoryStore(tmp_root)
        with pytest.raises(ValueError, match="Invalid memory scope"):
            store.read("../../../etc/passwd")

    def test_rejects_arbitrary_scope(self, tmp_root):
        store = MemoryStore(tmp_root)
        with pytest.raises(ValueError):
            store.write("evil_scope", "content")

    def test_accepts_valid_scopes(self, tmp_root):
        root = tmp_root
        store = MemoryStore(root)
        for scope in ("project", "decisions", "patterns"):
            store.write(scope, f"test content for {scope}")
            assert store.read(scope) == f"test content for {scope}"


class TestProjectStoreValidation:
    def test_create_rejects_traversal(self, tmp_root):
        root = tmp_root
        store = ProjectStore(root)
        store.init_board()
        with pytest.raises(ValueError):
            store.create_project("../../etc")

    def test_update_spec_rejects_nonexistent(self, tmp_root):
        root = tmp_root
        store = ProjectStore(root)
        store.init_board()
        with pytest.raises(FileNotFoundError):
            store.update_spec("nonexistent", "content")

    def test_update_plan_rejects_nonexistent(self, tmp_root):
        root = tmp_root
        store = ProjectStore(root)
        store.init_board()
        with pytest.raises(FileNotFoundError):
            store.update_plan("nonexistent", "content")
