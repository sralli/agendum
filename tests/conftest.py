"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Create a temporary .agentpm root directory."""
    root = tmp_path / ".agentpm"
    root.mkdir()
    return root
