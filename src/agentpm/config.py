"""Shared configuration for agentpm."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_root(home: bool = False) -> Path:
    """Resolve the .agentpm root directory.

    Priority: AGENTPM_ROOT env > AGENTPM_HOME env > --home flag > cwd/.agentpm
    """
    root_env = os.environ.get("AGENTPM_ROOT")
    if root_env:
        return Path(root_env)
    if home or os.environ.get("AGENTPM_HOME"):
        return Path.home() / ".agentpm"
    return Path.cwd() / ".agentpm"
