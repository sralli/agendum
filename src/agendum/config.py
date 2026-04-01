"""Shared configuration for agendum."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def resolve_root(home: bool = False) -> Path:
    """Resolve the .agendum root directory.

    Priority: AGENDUM_ROOT env > AGENDUM_HOME env > --home flag > cwd/.agendum

    Auto-migrates legacy .agentpm/ directory to .agendum/ on first use.
    """
    root_env = os.environ.get("AGENDUM_ROOT")
    if root_env:
        return Path(root_env)
    if home or os.environ.get("AGENDUM_HOME"):
        target = Path.home() / ".agendum"
        _migrate_if_needed(Path.home() / ".agentpm", target)
        return target
    target = Path.cwd() / ".agendum"
    _migrate_if_needed(Path.cwd() / ".agentpm", target)
    return target


def derive_board_name() -> str:
    """Derive a board name from git remote or directory name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except (subprocess.SubprocessError, OSError):
        pass
    return Path.cwd().name


def _migrate_if_needed(old: Path, new: Path) -> None:
    """Rename .agentpm/ → .agendum/ if old exists and new does not."""
    if old.exists() and not new.exists():
        shutil.move(str(old), str(new))
        print(f"[agendum] Migrated {old} → {new}")
