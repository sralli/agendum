"""Cross-platform file locking and atomic write utilities."""

from __future__ import annotations

import os
from pathlib import Path

from filelock import FileLock


def get_lock(path: Path) -> FileLock:
    """Return a FileLock using a .lock sidecar file next to the target."""
    return FileLock(str(path) + ".lock")


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content atomically: write to .tmp then os.replace() (POSIX-atomic)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding=encoding)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
