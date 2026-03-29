"""Tests for project store."""

import tempfile
from pathlib import Path

from agendum.store.project_store import ProjectStore


def _tmp_root():
    return Path(tempfile.mkdtemp()) / ".agentpm"


class TestProjectStore:
    def test_init_board(self):
        root = _tmp_root()
        store = ProjectStore(root)
        config = store.init_board("test-board")
        assert config.name == "test-board"
        assert (root / "projects").is_dir()
        assert (root / "agents").is_dir()
        assert (root / "memory").is_dir()
        assert (root / "config.yaml").exists()

    def test_create_project(self):
        root = _tmp_root()
        store = ProjectStore(root)
        store.init_board()
        project = store.create_project("webapp", "A web app")
        assert project.name == "webapp"
        assert (root / "projects" / "webapp" / "spec.md").exists()
        assert (root / "projects" / "webapp" / "plan.md").exists()
        assert (root / "projects" / "webapp" / "tasks").is_dir()

    def test_create_updates_config(self):
        root = _tmp_root()
        store = ProjectStore(root)
        store.init_board()
        store.create_project("alpha")
        store.create_project("beta")
        config = store.read_config()
        assert "alpha" in config.projects
        assert "beta" in config.projects
        assert config.default_project == "alpha"

    def test_get_project(self):
        root = _tmp_root()
        store = ProjectStore(root)
        store.init_board()
        store.create_project("test", "Description")
        project = store.get_project("test")
        assert project is not None
        assert "Description" in project.spec

    def test_get_nonexistent(self):
        root = _tmp_root()
        store = ProjectStore(root)
        store.init_board()
        assert store.get_project("nope") is None

    def test_update_spec(self):
        root = _tmp_root()
        store = ProjectStore(root)
        store.init_board()
        store.create_project("test")
        store.update_spec("test", "# New Spec\n\nUpdated content")
        project = store.get_project("test")
        assert "New Spec" in project.spec

    def test_list_projects(self):
        root = _tmp_root()
        store = ProjectStore(root)
        store.init_board()
        store.create_project("alpha")
        store.create_project("beta")
        projects = store.list_projects()
        assert projects == ["alpha", "beta"]
