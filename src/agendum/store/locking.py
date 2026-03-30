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


def atomic_create(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Create a file atomically. Raises FileExistsError if file already exists.

    Uses O_CREAT|O_EXCL for race-free creation.
    """
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, content.encode(encoding))
    finally:
        os.close(fd)


def next_sequential_id(directory: Path, prefix: str, extension: str, extra_dirs: list[Path] | None = None) -> str:
    """Generate the next sequential ID like prefix-001, prefix-002.

    Scans directory (and any extra_dirs) for files matching {prefix}-*.{extension}.
    """
    dirs = [directory] + (extra_dirs or [])
    max_num = 0
    for d in dirs:
        if not d.exists():
            continue
        for path in d.glob(f"{prefix}-*.{extension}"):
            parts = path.stem.split("-", 1)
            if len(parts) == 2:
                try:
                    max_num = max(max_num, int(parts[1]))
                except ValueError:
                    continue

    return f"{prefix}-{max_num + 1:03d}"
