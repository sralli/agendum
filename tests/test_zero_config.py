"""Tests for zero-config first run (Feature 9)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agendum.config import derive_board_name


class TestDeriveBoardName:
    def test_returns_git_toplevel_name(self, tmp_path):
        with patch("agendum.config.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = str(tmp_path / "my-project") + "\n"
            assert derive_board_name() == "my-project"

    def test_falls_back_to_cwd_on_git_failure(self, tmp_path):
        with patch("agendum.config.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 128
            with patch("agendum.config.Path.cwd", return_value=tmp_path / "fallback-dir"):
                assert derive_board_name() == "fallback-dir"

    def test_falls_back_to_cwd_on_exception(self, tmp_path):
        with patch("agendum.config.subprocess.run", side_effect=OSError("no git")):
            with patch("agendum.config.Path.cwd", return_value=tmp_path / "fallback-dir"):
                assert derive_board_name() == "fallback-dir"


class TestZeroConfigStores:
    """Test that _Stores auto-initializes .agendum/ on first access."""

    def test_auto_init_on_board_access(self, tmp_path):
        """Accessing stores.board auto-creates .agendum/ structure."""
        root = tmp_path / ".agendum"
        # root does NOT exist yet — no mkdir
        assert not root.exists()

        from agendum.server import _Stores

        stores = _Stores()
        stores._root = root  # bypass resolve_root

        # Access board — should trigger auto-init
        board = stores.board
        assert board is not None
        assert root.exists()
        assert (root / "config.yaml").exists()
        assert (root / "projects").is_dir()
        assert (root / "learnings").is_dir()
        assert (root / "memory").is_dir()

    def test_auto_init_on_project_access(self, tmp_path):
        """Accessing stores.project auto-creates .agendum/ structure."""
        root = tmp_path / ".agendum"
        assert not root.exists()

        from agendum.server import _Stores

        stores = _Stores()
        stores._root = root

        project = stores.project
        assert project is not None
        assert (root / "config.yaml").exists()

    def test_auto_init_on_memory_access(self, tmp_path):
        """Accessing stores.memory auto-creates .agendum/ structure."""
        root = tmp_path / ".agendum"
        assert not root.exists()

        from agendum.server import _Stores

        stores = _Stores()
        stores._root = root

        memory = stores.memory
        assert memory is not None
        assert (root / "config.yaml").exists()

    def test_auto_init_on_learnings_access(self, tmp_path):
        """Accessing stores.learnings auto-creates .agendum/ structure."""
        root = tmp_path / ".agendum"
        assert not root.exists()

        from agendum.server import _Stores

        stores = _Stores()
        stores._root = root

        learnings = stores.learnings
        assert learnings is not None
        assert (root / "config.yaml").exists()

    def test_no_reinit_if_already_exists(self, tmp_path):
        """If config.yaml already exists, don't re-initialize."""
        root = tmp_path / ".agendum"
        root.mkdir()
        (root / "projects").mkdir()
        (root / "learnings").mkdir()
        (root / "memory").mkdir()

        # Write a custom config
        config_path = root / "config.yaml"
        config_path.write_text("name: custom-board\nprojects: []\n")

        from agendum.server import _Stores

        stores = _Stores()
        stores._root = root

        # Access should NOT overwrite existing config
        _ = stores.board
        assert config_path.read_text().startswith("name: custom-board")

    def test_no_recursion_on_project_init(self, tmp_path):
        """Ensure accessing project during init doesn't cause infinite recursion."""
        root = tmp_path / ".agendum"
        assert not root.exists()

        from agendum.server import _Stores

        stores = _Stores()
        stores._root = root

        # This would cause infinite recursion if not handled:
        # project property -> _ensure_initialized -> self.project -> _ensure_initialized -> ...
        project_store = stores.project
        assert project_store is not None
        assert (root / "config.yaml").exists()


class TestZeroConfigIntegration:
    """Integration test: pm_project create works without pm_init."""

    @pytest.mark.asyncio
    async def test_pm_project_create_without_init(self, tmp_path):
        """pm_project create should work even if .agendum/ doesn't exist."""
        root = tmp_path / ".agendum"
        assert not root.exists()

        from mcp.server.fastmcp import FastMCP

        from agendum.enrichment.pipeline import ContextEnricher
        from agendum.enrichment.sources import DependencySource, MemorySource, ProjectRulesSource
        from agendum.server import _Stores
        from agendum.tools import register

        stores = _Stores()
        stores._root = root

        enricher = ContextEnricher()
        enricher.register(ProjectRulesSource(root))
        enricher.register(MemorySource(stores.memory))
        enricher.register(DependencySource(stores.board))

        mcp = FastMCP("agendum-test-zero-config")
        register(mcp, stores, enricher)

        from tests.conftest import call

        result = await call(mcp, "pm_project", action="create", name="myapp", description="My app")
        assert "myapp" in result
        assert "created" in result.lower()
        assert (root / "config.yaml").exists()
        assert (root / "projects" / "myapp").is_dir()
