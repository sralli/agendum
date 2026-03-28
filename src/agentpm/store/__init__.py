"""Store utilities shared across all store modules."""

from __future__ import annotations

import re

_UNSAFE_PATTERN = re.compile(r"[/\\]|\.\.|[\x00-\x1f]")


def sanitize_name(name: str) -> str:
    """Validate and sanitize a project or task ID name.

    Rejects path traversal attempts (../, /, \\, null bytes).
    """
    if not name or _UNSAFE_PATTERN.search(name):
        raise ValueError(f"Invalid name: {name!r} (contains path separators, '..', or control characters)")
    name = name.lstrip(".")
    if not name:
        raise ValueError("Name cannot be empty or only dots")
    return name
