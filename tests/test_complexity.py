"""Tests for complexity signal computation."""

from __future__ import annotations

from agendum.models import BoardItem
from agendum.tools import _compute_complexity


def _make_item(key_files=None, acceptance_criteria=None, depends_on=None) -> BoardItem:
    return BoardItem(
        id="item-001",
        project="test",
        title="Test task",
        key_files=key_files or [],
        acceptance_criteria=acceptance_criteria or [],
        depends_on=depends_on or [],
    )


def test_trivial_complexity():
    item = _make_item(key_files=[], acceptance_criteria=["one"])
    complexity, scope = _compute_complexity(item)
    assert complexity == "trivial"


def test_small_complexity():
    item = _make_item(key_files=["a.py", "b.py"], acceptance_criteria=["one", "two"], depends_on=["item-000"])
    complexity, scope = _compute_complexity(item)
    assert complexity == "small"


def test_medium_complexity():
    item = _make_item(
        key_files=["a.py", "b.py", "c.py", "d.py"],
        acceptance_criteria=["one", "two", "three"],
        depends_on=["item-000"],
    )
    complexity, scope = _compute_complexity(item)
    assert complexity == "medium"


def test_large_complexity():
    item = _make_item(
        key_files=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py", "h.py"],
        acceptance_criteria=["one", "two", "three", "four", "five"],
        depends_on=["item-000", "item-001", "item-002"],
    )
    complexity, scope = _compute_complexity(item)
    assert complexity == "large"


def test_complexity_clamps_to_valid_range():
    # Minimal everything should clamp to trivial, not go negative
    item = _make_item(key_files=[], acceptance_criteria=[], depends_on=[])
    complexity, scope = _compute_complexity(item)
    assert complexity == "trivial"


def test_estimated_scope_single_file():
    item = _make_item(key_files=["src/api.py"])
    _, scope = _compute_complexity(item)
    assert "Single-file" in scope
    assert "src/api.py" in scope


def test_estimated_scope_multi_file():
    item = _make_item(key_files=["a.py", "b.py", "c.py"])
    _, scope = _compute_complexity(item)
    assert "3-file" in scope
