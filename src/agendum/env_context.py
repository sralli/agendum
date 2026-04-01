"""Utilities for auto-detecting agent environment context."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path


def get_git_branch() -> str | None:
    """Return the current git branch name, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        branch = result.stdout.strip()
        return branch if result.returncode == 0 and branch and branch != "HEAD" else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_working_dir() -> str:
    """Return the current working directory as a string."""
    return str(Path.cwd())


def get_device_name() -> str | None:
    """Return the hostname as a device identifier."""
    try:
        return socket.gethostname()
    except OSError:
        return None


def get_git_diff_stat() -> str | None:
    """Get git diff --stat for the last commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--stat"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def get_last_commit_message() -> str | None:
    """Get the last commit message."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return None
