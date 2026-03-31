# Agendum v2 Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite agendum from a 32-tool orchestrator into an 11-tool Project Memory + Scoping Engine that augments (not competes with) the Claude Code harness.

**Architecture:** Keep the git-native file storage (Markdown+YAML), atomic locking, enrichment pipeline, and dependency graph. Cut agent coordination, orchestrator, model routing, and review gates. Add BoardItem model, WorkPackage for scoped dispatch, LearningsStore for cross-project knowledge, and pm_ingest for plan file parsing.

**Tech Stack:** Python 3.13+, FastMCP, Pydantic 2, uv, filelock, python-frontmatter, PyYAML

**Spec:** `docs/superpowers/specs/2026-03-31-agendum-v2-design.md`

---

### Task 1: Rewrite models.py — BoardItem, WorkPackage, cut orchestrator models

**Files:**
- Modify: `src/agendum/models.py`

- [ ] **Step 1: Read the current models.py**

Read `src/agendum/models.py` to understand all existing models.

- [ ] **Step 2: Write tests for new models**

Create `tests/test_models_v2.py`:

```python
"""Tests for v2 models: BoardItem, WorkPackage."""

from datetime import UTC, datetime

from agendum.models import BoardItem, TaskPriority, TaskStatus, TaskType, WorkPackage


class TestBoardItem:
    def test_defaults(self):
        item = BoardItem(id="item-001", project="demo", title="Test")
        assert item.status == TaskStatus.PENDING
        assert item.type == TaskType.DEV
        assert item.priority == TaskPriority.MEDIUM
        assert item.depends_on == []
        assert item.acceptance_criteria == []
        assert item.key_files == []
        assert item.constraints == []
        assert item.tags == []
        assert item.notes == ""
        assert item.progress == []
        assert item.decisions == []

    def test_all_fields(self):
        item = BoardItem(
            id="item-001",
            project="demo",
            title="Auth setup",
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.DEV,
            priority=TaskPriority.HIGH,
            depends_on=["item-000"],
            acceptance_criteria=["Login works"],
            key_files=["src/auth.py"],
            constraints=["No breaking changes"],
            tags=["auth"],
            notes="Use Clerk",
        )
        assert item.title == "Auth setup"
        assert item.depends_on == ["item-000"]


class TestWorkPackage:
    def test_from_item(self):
        item = BoardItem(id="item-001", project="demo", title="Test")
        pkg = WorkPackage(
            item=item,
            scope="Only modify auth files",
            exit_criteria=["Tests pass"],
            context="Decision: Using Clerk",
        )
        assert pkg.item.id == "item-001"
        assert pkg.scope == "Only modify auth files"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_models_v2.py -v`
Expected: ImportError — `BoardItem` and `WorkPackage` don't exist yet.

- [ ] **Step 4: Rewrite models.py**

Keep: `TaskStatus`, `TaskPriority`, `TaskType`, `ProgressEntry`, `MemoryEntry`, `BoardConfig`, `Project`

Cut: `Agent`, `AgentPersistenceRecord`, `AgentHandoffRecord`, `TaskCategory`, `ExecutionStatus`, `ApprovalPolicy`, `TaskCompletionStatus`, `ExecutionLevel`, `ContextPacket`, `ExecutionPlan`, `ExecutionTrace`, `ExternalReference`, `ModelRouting`, `ProjectPolicy`, `BoardStatus`, `Task`

Add:

```python
class BoardItem(BaseModel):
    """A persistent item on the project board."""
    id: str
    project: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    type: TaskType = TaskType.DEV
    priority: TaskPriority = TaskPriority.MEDIUM
    depends_on: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    progress: list[ProgressEntry] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)


class WorkPackage(BaseModel):
    """Bounded, context-rich unit of work returned by pm_next."""
    item: BoardItem
    scope: str = ""
    entry_criteria: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)
    context: str = ""
    constraints: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    dependency_context: str = ""
    memory_context: str = ""
    project_rules: str = ""
    pointers: list[str] = Field(default_factory=list)
```

Also simplify `BoardConfig` — remove `agent_routing` field if present.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_models_v2.py -v`
Expected: PASS

- [ ] **Step 6: Run ruff**

Run: `uv run ruff check src/agendum/models.py`
Expected: Clean

- [ ] **Step 7: Commit**

```bash
git add src/agendum/models.py tests/test_models_v2.py
git commit -m "refactor: rewrite models for v2 — BoardItem, WorkPackage, cut orchestrator models"
```

---

### Task 2: Adapt store layer — BoardStore, board_format, LearningsStore

**Files:**
- Create: `src/agendum/store/board_format.py` (adapted from `task_format.py`)
- Create: `src/agendum/store/board_store.py` (adapted from `task_store.py`)
- Create: `src/agendum/store/learnings_store.py`
- Modify: `src/agendum/store/memory_store.py` (add `learnings` scope)
- Modify: `src/agendum/store/project_store.py` (remove policy, change `tasks/` to `board/`)
- Test: `tests/test_board_store.py`, `tests/test_board_format.py`, `tests/test_learnings_store.py`

- [ ] **Step 1: Write board_format.py tests**

Create `tests/test_board_format.py`:

```python
"""Tests for board item Markdown serialization."""

from pathlib import Path

from agendum.models import BoardItem, TaskPriority, TaskStatus
from agendum.store.board_format import board_item_from_file, board_item_to_markdown


class TestBoardFormat:
    def test_roundtrip_minimal(self, tmp_path):
        item = BoardItem(id="item-001", project="demo", title="Test item")
        md = board_item_to_markdown(item)
        path = tmp_path / "item-001.md"
        path.write_text(md)
        recovered = board_item_from_file(path)
        assert recovered.id == "item-001"
        assert recovered.title == "Test item"
        assert recovered.status == TaskStatus.PENDING

    def test_roundtrip_full(self, tmp_path):
        item = BoardItem(
            id="item-002",
            project="demo",
            title="Auth setup",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            depends_on=["item-001"],
            blocks=["item-003"],
            acceptance_criteria=["Login works", "Logout works"],
            key_files=["src/auth.py"],
            constraints=["No breaking changes"],
            tags=["auth"],
            notes="Use Clerk for auth",
        )
        md = board_item_to_markdown(item)
        path = tmp_path / "item-002.md"
        path.write_text(md)
        recovered = board_item_from_file(path)
        assert recovered.title == "Auth setup"
        assert recovered.depends_on == ["item-001"]
        assert recovered.blocks == ["item-003"]
        assert len(recovered.acceptance_criteria) == 2
        assert recovered.notes == "Use Clerk for auth"

    def test_progress_roundtrip(self, tmp_path):
        item = BoardItem(id="item-001", project="demo", title="Test")
        from agendum.models import ProgressEntry
        from datetime import datetime, UTC
        item.progress = [ProgressEntry(timestamp=datetime.now(UTC), agent="claude", message="Started")]
        md = board_item_to_markdown(item)
        path = tmp_path / "item-001.md"
        path.write_text(md)
        recovered = board_item_from_file(path)
        assert len(recovered.progress) == 1
        assert recovered.progress[0].message == "Started"

    def test_decisions_roundtrip(self, tmp_path):
        item = BoardItem(id="item-001", project="demo", title="Test", decisions=["Chose Clerk over Auth0"])
        md = board_item_to_markdown(item)
        path = tmp_path / "item-001.md"
        path.write_text(md)
        recovered = board_item_from_file(path)
        assert recovered.decisions == ["Chose Clerk over Auth0"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_board_format.py -v`
Expected: ImportError — `board_format` doesn't exist yet.

- [ ] **Step 3: Implement board_format.py**

Adapt from `task_format.py`. Key changes:
- Rename functions: `task_from_file` → `board_item_from_file`, `task_to_markdown` → `board_item_to_markdown`
- Map to `BoardItem` fields instead of `Task`
- Remove handoff/structured_handoff/agent_history sections
- Add `## Notes` section for the `notes` field
- Keep `## Context` → mapped to `notes` field (or separate, your choice — but keep it simple)
- Keep `## Progress`, `## Decisions` sections
- Remove `## Artifacts`, `## Handoff`, `## Agent History`
- Frontmatter keys use snake_case: `depends_on`, `key_files`, `acceptance_criteria`

```python
"""Board item ↔ Markdown+YAML serialization."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from agendum.models import BoardItem, ProgressEntry, TaskPriority, TaskStatus, TaskType


def board_item_from_file(path: Path) -> BoardItem:
    """Parse a Markdown file with YAML frontmatter into a BoardItem."""
    post = frontmatter.load(str(path))
    meta = post.metadata
    body = post.content

    progress = _extract_progress(body)
    decisions = _extract_list_items(body, "Decisions")
    notes = _extract_section(body, "Notes")

    return BoardItem(
        id=meta.get("id", ""),
        project=meta.get("project", ""),
        title=meta.get("title", ""),
        status=_safe_enum(TaskStatus, meta.get("status", "pending")),
        type=_safe_enum(TaskType, meta.get("type", "dev")),
        priority=_safe_enum(TaskPriority, meta.get("priority", "medium")),
        depends_on=_ensure_list(meta.get("depends_on", [])),
        blocks=_ensure_list(meta.get("blocks", [])),
        acceptance_criteria=_ensure_list(meta.get("acceptance_criteria", [])),
        key_files=_ensure_list(meta.get("key_files", [])),
        constraints=_ensure_list(meta.get("constraints", [])),
        tags=_ensure_list(meta.get("tags", [])),
        notes=notes,
        created=_parse_dt(meta.get("created")),
        updated=_parse_dt(meta.get("updated")),
        progress=progress,
        decisions=decisions,
    )


def board_item_to_markdown(item: BoardItem) -> str:
    """Serialize a BoardItem to Markdown with YAML frontmatter."""
    meta = {
        "id": item.id,
        "project": item.project,
        "title": item.title,
        "status": item.status.value,
        "type": item.type.value,
        "priority": item.priority.value,
        "depends_on": item.depends_on,
        "blocks": item.blocks,
        "acceptance_criteria": item.acceptance_criteria,
        "key_files": item.key_files,
        "constraints": item.constraints,
        "tags": item.tags,
        "created": item.created.isoformat(),
        "updated": item.updated.isoformat(),
    }

    sections = []

    if item.notes:
        sections.append(f"## Notes\n{item.notes}")

    if item.progress:
        lines = []
        for p in item.progress:
            ts = p.timestamp.strftime("%Y-%m-%dT%H:%MZ")
            agent_part = f" {p.agent}" if p.agent else ""
            lines.append(f"- **[{ts}]{agent_part}** — {p.message}")
        sections.append("## Progress\n" + "\n".join(lines))

    if item.decisions:
        lines = [f"- {d}" for d in item.decisions]
        sections.append("## Decisions\n" + "\n".join(lines))

    post = frontmatter.Post(content="\n\n".join(sections), **meta)
    return frontmatter.dumps(post) + "\n"
```

Include the helper functions: `_extract_section`, `_extract_list_items`, `_extract_progress`, `_ensure_list`, `_safe_enum`, `_parse_dt` — adapted from `task_format.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_board_format.py -v`
Expected: PASS

- [ ] **Step 5: Write board_store.py tests**

Create `tests/test_board_store.py`:

```python
"""Tests for BoardStore: file I/O, CRUD."""

import pytest

from agendum.models import TaskStatus
from agendum.store.board_store import BoardStore


class TestBoardStore:
    def test_create_item(self, tmp_root):
        store = BoardStore(tmp_root)
        item = store.create_item("demo", "Setup project", priority="high")
        assert item.id == "item-001"
        assert item.title == "Setup project"
        assert item.status == TaskStatus.PENDING

    def test_sequential_ids(self, tmp_root):
        store = BoardStore(tmp_root)
        i1 = store.create_item("demo", "First")
        i2 = store.create_item("demo", "Second")
        assert i1.id == "item-001"
        assert i2.id == "item-002"

    def test_get_item(self, tmp_root):
        store = BoardStore(tmp_root)
        created = store.create_item("demo", "Test", priority="critical")
        fetched = store.get_item("demo", created.id)
        assert fetched is not None
        assert fetched.title == "Test"

    def test_get_nonexistent(self, tmp_root):
        store = BoardStore(tmp_root)
        assert store.get_item("demo", "item-999") is None

    def test_list_items(self, tmp_root):
        store = BoardStore(tmp_root)
        store.create_item("demo", "A")
        store.create_item("demo", "B")
        items = store.list_items("demo")
        assert len(items) == 2

    def test_list_with_status_filter(self, tmp_root):
        store = BoardStore(tmp_root)
        store.create_item("demo", "A")
        store.create_item("demo", "B")
        store.update_item("demo", "item-001", status=TaskStatus.IN_PROGRESS)
        pending = store.list_items("demo", status=TaskStatus.PENDING)
        assert len(pending) == 1

    def test_update_item(self, tmp_root):
        store = BoardStore(tmp_root)
        store.create_item("demo", "Original")
        updated = store.update_item("demo", "item-001", status=TaskStatus.IN_PROGRESS)
        assert updated.status == TaskStatus.IN_PROGRESS

    def test_add_progress(self, tmp_root):
        store = BoardStore(tmp_root)
        store.create_item("demo", "Test")
        store.add_progress("demo", "item-001", "claude", "Started work")
        item = store.get_item("demo", "item-001")
        assert len(item.progress) == 1

    def test_done_items_accessible(self, tmp_root):
        store = BoardStore(tmp_root)
        store.create_item("demo", "Done item")
        store.update_item("demo", "item-001", status=TaskStatus.DONE)
        item = store.get_item("demo", "item-001")
        assert item is not None
        assert item.status == TaskStatus.DONE
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_board_store.py -v`
Expected: ImportError

- [ ] **Step 7: Implement board_store.py**

Adapt from `task_store.py`. Key changes:
- Class name: `BoardStore`
- Directory: `board/` instead of `tasks/`
- Prefix: `item-` instead of `task-`
- Use `board_item_from_file` / `board_item_to_markdown` from `board_format.py`
- Remove `archive_task`, `list_archived_tasks`, `all_tasks` — done items stay in `board/` directory (no separate archive)
- Remove agent-specific fields from `_MUTABLE_FIELDS`
- Method renames: `create_task` → `create_item`, `get_task` → `get_item`, etc.

```python
"""File-backed board item storage with atomic writes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agendum.models import BoardItem, ProgressEntry, TaskPriority, TaskStatus, TaskType
from agendum.store.board_format import board_item_from_file, board_item_to_markdown
from agendum.store.locking import atomic_write, get_lock, next_sequential_id

_MUTABLE_FIELDS = frozenset({
    "status", "priority", "type", "depends_on", "blocks",
    "acceptance_criteria", "key_files", "constraints", "tags",
    "notes", "decisions",
})


class BoardStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _board_dir(self, project: str) -> Path:
        return self._root / "projects" / project / "board"

    def _item_path(self, project: str, item_id: str) -> Path:
        return self._board_dir(project) / f"{item_id}.md"

    def _next_item_id(self, project: str) -> str:
        return next_sequential_id(self._board_dir(project), "item", "md")

    def ensure_project(self, project: str) -> None:
        self._board_dir(project).mkdir(parents=True, exist_ok=True)

    def create_item(self, project: str, title: str, **kwargs) -> BoardItem:
        self.ensure_project(project)
        item_id = self._next_item_id(project)
        now = datetime.now(UTC)
        item = BoardItem(
            id=item_id,
            project=project,
            title=title,
            created=now,
            updated=now,
            **{k: v for k, v in kwargs.items() if v is not None},
        )
        path = self._item_path(project, item_id)
        atomic_write(path, board_item_to_markdown(item))
        return item

    def get_item(self, project: str, item_id: str) -> BoardItem | None:
        path = self._item_path(project, item_id)
        if not path.exists():
            return None
        return board_item_from_file(path)

    def list_items(self, project: str, status=None, tag=None, item_type=None) -> list[BoardItem]:
        board_dir = self._board_dir(project)
        if not board_dir.exists():
            return []
        items = []
        for p in sorted(board_dir.glob("item-*.md")):
            item = board_item_from_file(p)
            if status and item.status != status:
                continue
            if tag and tag not in item.tags:
                continue
            if item_type and item.type.value != item_type:
                continue
            items.append(item)
        return items

    def update_item(self, project: str, item_id: str, **updates) -> BoardItem | None:
        path = self._item_path(project, item_id)
        if not path.exists():
            return None
        with get_lock(path):
            item = board_item_from_file(path)
            for key, value in updates.items():
                if key in _MUTABLE_FIELDS:
                    if key == "status":
                        value = TaskStatus(value) if isinstance(value, str) else value
                    elif key == "priority":
                        value = TaskPriority(value) if isinstance(value, str) else value
                    elif key == "type":
                        value = TaskType(value) if isinstance(value, str) else value
                    setattr(item, key, value)
            item.updated = datetime.now(UTC)
            atomic_write(path, board_item_to_markdown(item))
        return item

    def add_progress(self, project: str, item_id: str, agent: str, message: str) -> BoardItem | None:
        path = self._item_path(project, item_id)
        if not path.exists():
            return None
        with get_lock(path):
            item = board_item_from_file(path)
            item.progress.append(ProgressEntry(timestamp=datetime.now(UTC), agent=agent, message=message))
            item.updated = datetime.now(UTC)
            atomic_write(path, board_item_to_markdown(item))
        return item

    def delete_item(self, project: str, item_id: str) -> bool:
        path = self._item_path(project, item_id)
        if not path.exists():
            return False
        path.unlink()
        lock_path = path.with_suffix(".md.lock")
        if lock_path.exists():
            lock_path.unlink()
        return True
```

- [ ] **Step 8: Run board_store tests**

Run: `uv run pytest tests/test_board_store.py -v`
Expected: PASS

- [ ] **Step 9: Write learnings_store.py tests**

Create `tests/test_learnings_store.py`:

```python
"""Tests for LearningsStore: global cross-project knowledge."""

from agendum.store.learnings_store import LearningsStore


class TestLearningsStore:
    def test_add_learning(self, tmp_root):
        store = LearningsStore(tmp_root)
        learning = store.add_learning("proxy.ts must be at same level as app/", tags=["nextjs", "clerk"])
        assert learning["id"].startswith("learning-")
        assert "proxy.ts" in learning["content"]

    def test_list_learnings(self, tmp_root):
        store = LearningsStore(tmp_root)
        store.add_learning("Use Clerk for auth", tags=["auth"])
        store.add_learning("proxy.ts gotcha", tags=["nextjs"])
        all_learnings = store.list_learnings()
        assert len(all_learnings) == 2

    def test_list_by_tag(self, tmp_root):
        store = LearningsStore(tmp_root)
        store.add_learning("Auth tip", tags=["auth"])
        store.add_learning("Next tip", tags=["nextjs"])
        auth_only = store.list_learnings(tag="auth")
        assert len(auth_only) == 1
        assert "Auth tip" in auth_only[0]["content"]

    def test_search_learnings(self, tmp_root):
        store = LearningsStore(tmp_root)
        store.add_learning("Clerk needs NEXT_PUBLIC_CLERK_SIGN_IN_URL", tags=["clerk"])
        store.add_learning("Use Neon for Postgres", tags=["db"])
        results = store.search_learnings("clerk")
        assert len(results) == 1
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `uv run pytest tests/test_learnings_store.py -v`
Expected: ImportError

- [ ] **Step 11: Implement learnings_store.py**

```python
"""Global cross-project learnings store."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from agendum.store.locking import atomic_write, get_lock, next_sequential_id


class LearningsStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._dir = root / "learnings"

    def ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def add_learning(
        self,
        content: str,
        tags: list[str] | None = None,
        source_project: str | None = None,
    ) -> dict:
        self.ensure_dir()
        learning_id = next_sequential_id(self._dir, "learning", "md")
        meta = {
            "id": learning_id,
            "tags": tags or [],
            "source_project": source_project or "",
            "created": datetime.now(UTC).isoformat(),
        }
        post = frontmatter.Post(content=content, **meta)
        path = self._dir / f"{learning_id}.md"
        atomic_write(path, frontmatter.dumps(post) + "\n")
        return {"id": learning_id, "content": content, "tags": tags or []}

    def list_learnings(self, tag: str | None = None) -> list[dict]:
        if not self._dir.exists():
            return []
        results = []
        for p in sorted(self._dir.glob("learning-*.md")):
            post = frontmatter.load(str(p))
            tags = post.metadata.get("tags", [])
            if tag and tag not in tags:
                continue
            results.append({
                "id": post.metadata.get("id", p.stem),
                "content": post.content,
                "tags": tags,
                "source_project": post.metadata.get("source_project", ""),
                "created": post.metadata.get("created", ""),
            })
        return results

    def search_learnings(self, query: str) -> list[dict]:
        if not self._dir.exists():
            return []
        query_lower = query.lower()
        results = []
        for p in sorted(self._dir.glob("learning-*.md")):
            post = frontmatter.load(str(p))
            content = post.content.lower()
            tags = [t.lower() for t in post.metadata.get("tags", [])]
            if query_lower in content or any(query_lower in t for t in tags):
                results.append({
                    "id": post.metadata.get("id", p.stem),
                    "content": post.content,
                    "tags": post.metadata.get("tags", []),
                    "source_project": post.metadata.get("source_project", ""),
                })
        return results
```

- [ ] **Step 12: Run learnings_store tests**

Run: `uv run pytest tests/test_learnings_store.py -v`
Expected: PASS

- [ ] **Step 13: Update memory_store.py — add learnings scope**

In `src/agendum/store/memory_store.py`, change:
```python
SCOPES = ("project", "decisions", "patterns")
```
to:
```python
SCOPES = ("project", "decisions", "patterns", "learnings")
```

- [ ] **Step 14: Update project_store.py — remove policy, change tasks/ to board/**

In `src/agendum/store/project_store.py`:
- Remove `get_policy`, `update_policy`, `_policy_path` methods
- Remove `ProjectPolicy` import
- In `create_project`, change `tasks_dir` to use `board` instead of `tasks`
- In `init_board`, remove `agents_dir` creation, add `learnings_dir` creation

- [ ] **Step 15: Run all store tests**

Run: `uv run pytest tests/test_board_store.py tests/test_board_format.py tests/test_learnings_store.py tests/test_memory_store.py -v`
Expected: All PASS

- [ ] **Step 16: Run ruff**

Run: `uv run ruff check src/agendum/store/`
Expected: Clean

- [ ] **Step 17: Commit**

```bash
git add src/agendum/store/board_format.py src/agendum/store/board_store.py src/agendum/store/learnings_store.py src/agendum/store/memory_store.py src/agendum/store/project_store.py tests/test_board_store.py tests/test_board_format.py tests/test_learnings_store.py
git commit -m "feat: add BoardStore, board_format, LearningsStore for v2"
```

---

### Task 3: Move enrichment pipeline to core and adapt for BoardItem

**Files:**
- Create: `src/agendum/enrichment/__init__.py`
- Create: `src/agendum/enrichment/pipeline.py` (from `tools/orchestrator/enrichment.py`)
- Create: `src/agendum/enrichment/sources.py` (from `tools/orchestrator/sources.py`)
- Test: `tests/test_enrichment_v2.py`

- [ ] **Step 1: Write enrichment tests for v2**

Create `tests/test_enrichment_v2.py`:

```python
"""Tests for v2 enrichment pipeline with BoardItem."""

from agendum.enrichment.pipeline import ContextEnricher, ContextSource
from agendum.models import BoardItem, WorkPackage


class FakeSource:
    name = "fake"

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        return package.model_copy(update={"memory_context": "fake context injected"})


class TestEnrichmentPipeline:
    def test_register_and_enrich(self):
        enricher = ContextEnricher()
        enricher.register(FakeSource())
        item = BoardItem(id="item-001", project="demo", title="Test")
        package = WorkPackage(item=item)
        result = enricher.enrich(package, item, "demo")
        assert result.memory_context == "fake context injected"

    def test_empty_enricher(self):
        enricher = ContextEnricher()
        item = BoardItem(id="item-001", project="demo", title="Test")
        package = WorkPackage(item=item)
        result = enricher.enrich(package, item, "demo")
        assert result.memory_context == ""

    def test_budget_truncation(self):
        class BigSource:
            name = "big"
            def enrich(self, package, item, project):
                return package.model_copy(update={"project_rules": "x" * 10000})

        enricher = ContextEnricher()
        enricher.register(BigSource())
        item = BoardItem(id="item-001", project="demo", title="Test")
        package = WorkPackage(item=item)
        result = enricher.enrich(package, item, "demo", max_context_chars=5000)
        assert len(result.project_rules) < 10000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_enrichment_v2.py -v`
Expected: ImportError

- [ ] **Step 3: Create enrichment package**

Create `src/agendum/enrichment/__init__.py`:
```python
"""Context enrichment pipeline for work packages."""
```

- [ ] **Step 4: Implement pipeline.py**

Adapt `tools/orchestrator/enrichment.py` for `WorkPackage` and `BoardItem`:

```python
"""Pluggable context enrichment pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agendum.models import BoardItem, WorkPackage


@runtime_checkable
class ContextSource(Protocol):
    name: str

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage: ...


class ContextEnricher:
    def __init__(self) -> None:
        self._sources: list[ContextSource] = []

    def register(self, source: ContextSource) -> None:
        self._sources.append(source)

    def unregister(self, name: str) -> None:
        self._sources = [s for s in self._sources if s.name != name]

    @property
    def source_names(self) -> list[str]:
        return [s.name for s in self._sources]

    def enrich(
        self,
        package: WorkPackage,
        item: BoardItem,
        project: str,
        *,
        disabled_sources: list[str] | None = None,
        max_context_chars: int = 8000,
    ) -> WorkPackage:
        disabled = set(disabled_sources or [])
        for source in self._sources:
            if source.name in disabled:
                continue
            package = source.enrich(package, item, project)
        return self._apply_budget(package, max_context_chars)

    def _apply_budget(self, package: WorkPackage, max_chars: int) -> WorkPackage:
        budget = {
            "project_rules": 3000,
            "dependency_context": 2000,
            "memory_context": 2000,
        }
        updates = {}
        for field, limit in budget.items():
            value = getattr(package, field, "")
            if len(value) > limit:
                cut = value[:limit]
                last_nl = cut.rfind("\n")
                if last_nl > 0:
                    cut = cut[:last_nl]
                updates[field] = cut + f"\n...({field} truncated)"
        if updates:
            return package.model_copy(update=updates)
        return package
```

- [ ] **Step 5: Implement sources.py**

Adapt from `tools/orchestrator/sources.py`. Keep:
- `ProjectRulesSource` — adapted for `WorkPackage` (sets `project_rules` field)
- `MemorySource` — adapted for `WorkPackage` (sets `memory_context` field)
- `DependencySource` (renamed from `HandoffSource`) — reads completed dependency items' decisions/notes, sets `dependency_context`

Remove:
- `ReviewHistorySource` — no more review gates
- `ExternalReferencesSource` — no more ProjectPolicy

```python
"""Context enrichment sources for work packages."""

from __future__ import annotations

from pathlib import Path

from agendum.models import BoardItem, WorkPackage
from agendum.store.board_store import BoardStore
from agendum.store.memory_store import MemoryStore


def _find_git_root(start: Path, max_depth: int = 10) -> Path | None:
    current = start.resolve()
    for _ in range(max_depth):
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


class ProjectRulesSource:
    name = "project_rules"

    def __init__(self, agendum_root: Path, max_chars: int = 3000) -> None:
        self._root = agendum_root
        self._max_chars = max_chars

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        git_root = _find_git_root(self._root)
        if not git_root:
            return package
        for name in ("CLAUDE.md", "AGENTS.md"):
            path = git_root / name
            if path.exists():
                content = path.read_text(encoding="utf-8")[: self._max_chars]
                pointers = list(package.pointers) + [f"Full file: {path}"]
                return package.model_copy(update={"project_rules": content, "pointers": pointers})
        return package


class MemorySource:
    name = "memory"

    def __init__(self, memory_store: MemoryStore) -> None:
        self._memory = memory_store

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        query = item.title
        results = self._memory.search(query)
        if not results:
            return package
        lines = []
        for scope, matches in results.items():
            for match in matches[:5]:
                lines.append(f"- [{scope}] {match.strip()}")
        if not lines:
            return package
        context = "\n".join(lines)
        pointers = list(package.pointers)
        for scope in results:
            pointers.append(f'pm_memory(action="read", scope="{scope}")')
        return package.model_copy(update={"memory_context": context, "pointers": pointers})


class DependencySource:
    name = "dependencies"

    def __init__(self, board_store: BoardStore) -> None:
        self._store = board_store

    def enrich(self, package: WorkPackage, item: BoardItem, project: str) -> WorkPackage:
        if not item.depends_on:
            return package
        lines = []
        for dep_id in item.depends_on:
            dep = self._store.get_item(project, dep_id)
            if not dep:
                continue
            lines.append(f"### {dep.id}: {dep.title} [{dep.status.value}]")
            if dep.decisions:
                for d in dep.decisions[:5]:
                    lines.append(f"- Decision: {d}")
            if dep.notes:
                lines.append(f"- Notes: {dep.notes[:500]}")
        if not lines:
            return package
        return package.model_copy(update={"dependency_context": "\n".join(lines)})
```

- [ ] **Step 6: Run enrichment tests**

Run: `uv run pytest tests/test_enrichment_v2.py -v`
Expected: PASS

- [ ] **Step 7: Run ruff**

Run: `uv run ruff check src/agendum/enrichment/`
Expected: Clean

- [ ] **Step 8: Commit**

```bash
git add src/agendum/enrichment/ tests/test_enrichment_v2.py
git commit -m "feat: move enrichment pipeline to core, adapt for BoardItem/WorkPackage"
```

---

### Task 4: Implement the 11 MCP tools

**Files:**
- Create: `src/agendum/tools.py`
- Test: `tests/test_tools_v2.py`, `tests/test_ingest.py`

- [ ] **Step 1: Write integration tests for core tools**

Create `tests/test_tools_v2.py`:

```python
"""Integration tests for v2 MCP tools."""

import pytest
from tests.conftest import call


class TestPmInit:
    async def test_init(self, v2_server):
        mcp, stores = v2_server
        result = await call(mcp, "pm_init")
        assert "initialized" in result.lower() or "Board" in result


class TestPmProject:
    async def test_create_project(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        result = await call(mcp, "pm_project", action="create", name="myapp", description="Test app")
        assert "myapp" in result

    async def test_list_projects(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="app1")
        await call(mcp, "pm_project", action="create", name="app2")
        result = await call(mcp, "pm_project", action="list")
        assert "app1" in result
        assert "app2" in result

    async def test_get_project(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="myapp", description="My app")
        result = await call(mcp, "pm_project", action="get", name="myapp")
        assert "myapp" in result


class TestPmAdd:
    async def test_add_item(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="myapp")
        result = await call(mcp, "pm_add", project="myapp", title="Add auth")
        assert "item-001" in result

    async def test_add_with_metadata(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="myapp")
        result = await call(mcp, "pm_add", project="myapp", title="Auth", priority="high", tags="auth,security")
        assert "item-001" in result


class TestPmBoard:
    async def test_board_view(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="myapp")
        await call(mcp, "pm_add", project="myapp", title="Task A")
        await call(mcp, "pm_add", project="myapp", title="Task B")
        result = await call(mcp, "pm_board", project="myapp")
        assert "Task A" in result
        assert "Task B" in result


class TestPmStatus:
    async def test_status_brief(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="myapp")
        await call(mcp, "pm_add", project="myapp", title="Task A")
        result = await call(mcp, "pm_status", project="myapp")
        assert "myapp" in result


class TestPmNextAndDone:
    async def test_next_returns_work_package(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="myapp")
        await call(mcp, "pm_add", project="myapp", title="Setup auth", acceptance_criteria="Login works,Logout works")
        result = await call(mcp, "pm_next", project="myapp")
        assert "Setup auth" in result
        assert "Login works" in result

    async def test_done_updates_memory(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="myapp")
        await call(mcp, "pm_add", project="myapp", title="Auth")
        await call(mcp, "pm_next", project="myapp")
        result = await call(mcp, "pm_done", project="myapp", item_id="item-001", decisions="Chose Clerk over Auth0")
        assert "done" in result.lower() or "completed" in result.lower()
        # Verify memory was updated
        mem = await call(mcp, "pm_memory", action="read", scope="decisions")
        assert "Clerk" in mem


class TestPmBlock:
    async def test_block_item(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="myapp")
        await call(mcp, "pm_add", project="myapp", title="Blocked task")
        result = await call(mcp, "pm_block", project="myapp", item_id="item-001", reason="Waiting on API key")
        assert "blocked" in result.lower()


class TestPmMemory:
    async def test_memory_append_and_read(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_memory", action="append", scope="decisions", content="Use Clerk for auth")
        result = await call(mcp, "pm_memory", action="read", scope="decisions")
        assert "Clerk" in result

    async def test_memory_search(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_memory", action="append", scope="patterns", content="proxy.ts goes at project root")
        result = await call(mcp, "pm_memory", action="search", query="proxy")
        assert "proxy" in result


class TestPmLearn:
    async def test_learn(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        result = await call(mcp, "pm_learn", content="Clerk needs SIGN_IN_URL env var", tags="clerk,auth")
        assert "learning" in result.lower()
```

- [ ] **Step 2: Write pm_ingest tests**

Create `tests/test_ingest.py`:

```python
"""Tests for pm_ingest plan file parsing."""

from pathlib import Path

import pytest
from tests.conftest import call


SAMPLE_PLAN = """# Auth System Plan

## Task 1: Install Clerk SDK
- Install @clerk/nextjs
- Configure environment variables

**Acceptance Criteria:**
- Clerk SDK installed
- .env.local has CLERK_SECRET_KEY

**Files:** src/app/layout.tsx

## Task 2: Create sign-in pages
- Create /sign-in and /sign-up routes

**Acceptance Criteria:**
- Sign-in page renders
- Sign-up page renders

**Files:** src/app/sign-in/[[...sign-in]]/page.tsx, src/app/sign-up/[[...sign-up]]/page.tsx
**Depends:** Task 1

## Task 3: Add middleware protection
- Protect /dashboard routes

**Acceptance Criteria:**
- Dashboard redirects to sign-in when unauthenticated
- Public routes remain accessible

**Files:** src/proxy.ts
**Depends:** Task 1, Task 2
"""


class TestPmIngest:
    async def test_ingest_creates_items(self, v2_server, tmp_path):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="auth")

        plan_file = tmp_path / "plan.md"
        plan_file.write_text(SAMPLE_PLAN)

        result = await call(mcp, "pm_ingest", project="auth", plan_file=str(plan_file))
        assert "3" in result  # 3 items created
        assert "item-001" in result or "items" in result.lower()

    async def test_ingest_sets_dependencies(self, v2_server, tmp_path):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="auth")

        plan_file = tmp_path / "plan.md"
        plan_file.write_text(SAMPLE_PLAN)
        await call(mcp, "pm_ingest", project="auth", plan_file=str(plan_file))

        board = await call(mcp, "pm_board", project="auth")
        assert "item-001" in board

    async def test_ingest_nonexistent_file(self, v2_server):
        mcp, stores = v2_server
        await call(mcp, "pm_init")
        await call(mcp, "pm_project", action="create", name="auth")
        result = await call(mcp, "pm_ingest", project="auth", plan_file="/nonexistent/plan.md")
        assert "error" in result.lower() or "not found" in result.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_v2.py tests/test_ingest.py -v`
Expected: ImportError (tools.py doesn't exist, v2_server fixture doesn't exist)

- [ ] **Step 4: Implement tools.py — the 11 MCP tools**

Create `src/agendum/tools.py` with all 11 tools. Each tool is a closure registered via `register(mcp, stores, enricher)`. Tools return strings (never raise).

Key implementation details for each tool:

**pm_init** — wraps `stores.project.init_board()`

**pm_project** — action multiplexer: create/list/get

**pm_status** — builds a concise brief:
```
## Project: {name}
**Board:** {pending} pending, {in_progress} in progress, {done} done, {blocked} blocked
**Recent decisions:** {last 3 from memory}
**Next up:** {suggested item from find_unblocked_tasks}
```

**pm_add** — creates a BoardItem. Parse CSV strings for list fields (tags, acceptance_criteria, key_files, constraints, depends_on).

**pm_board** — lists items, formatted as compact table.

**pm_ingest** — the plan parser:
1. Read the file
2. Parse `## Task N:` or `### Task N:` headings as items
3. Bullets under heading → notes
4. `**Acceptance Criteria:**` bullets → acceptance_criteria
5. `**Files:**` → key_files (comma-separated)
6. `**Depends:**` → depends_on (maps `Task N` → `item-00N`)
7. Create BoardItems via store
8. Run `detect_cycles` and `topological_levels`
9. Return summary

**pm_next** — finds next unblocked item, builds WorkPackage, enriches it, marks in_progress, returns formatted markdown.

**pm_done** — marks done, appends decisions/patterns to memory, calls `resolve_completions` to unblock dependents.

**pm_block** — marks blocked, adds progress entry with reason.

**pm_memory** — delegates to MemoryStore methods based on action.

**pm_learn** — delegates to LearningsStore.add_learning.

The full implementation is ~400-500 lines. Each tool follows the pattern:
```python
@mcp.tool()
def pm_tool_name(param: type = default) -> str:
    try:
        # ... logic ...
        return "Success message"
    except Exception as e:
        return f"Error: {e}"
```

- [ ] **Step 5: Update conftest.py — add v2_server fixture**

Add to `tests/conftest.py`:

```python
@pytest_asyncio.fixture
async def v2_server(tmp_path: Path):
    """Fresh FastMCP instance with v2 stores and tools."""
    root = tmp_path / ".agendum"
    root.mkdir()

    from agendum.server import _Stores
    from agendum.store.board_store import BoardStore
    from agendum.store.learnings_store import LearningsStore
    from agendum.enrichment.pipeline import ContextEnricher
    from agendum.enrichment.sources import ProjectRulesSource, MemorySource, DependencySource

    stores = _Stores()
    stores._root = root
    # Ensure stores use new BoardStore
    stores._board = BoardStore(root)

    enricher = ContextEnricher()
    enricher.register(ProjectRulesSource(root))
    enricher.register(MemorySource(stores.memory))
    enricher.register(DependencySource(stores._board))

    mcp = FastMCP("agendum-test-v2")

    from agendum.tools import register
    register(mcp, stores, enricher)

    return mcp, stores
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_tools_v2.py tests/test_ingest.py -v`
Expected: PASS

- [ ] **Step 7: Run ruff**

Run: `uv run ruff check src/agendum/tools.py`
Expected: Clean

- [ ] **Step 8: Commit**

```bash
git add src/agendum/tools.py tests/test_tools_v2.py tests/test_ingest.py tests/conftest.py
git commit -m "feat: implement 11 v2 MCP tools — pm_init through pm_learn"
```

---

### Task 5: Rewire server.py and delete old modules

**Files:**
- Modify: `src/agendum/server.py`
- Delete: `src/agendum/tools/` (entire directory)
- Delete: `src/agendum/store/agent_store.py`
- Delete: `src/agendum/store/plan_store.py`
- Delete: `src/agendum/store/task_store.py`
- Delete: `src/agendum/store/task_format.py`

- [ ] **Step 1: Rewrite server.py**

```python
"""agendum MCP server — Project Memory + Scoping Engine."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from agendum.config import resolve_root
from agendum.enrichment.pipeline import ContextEnricher
from agendum.enrichment.sources import DependencySource, MemorySource, ProjectRulesSource
from agendum.store.board_store import BoardStore
from agendum.store.learnings_store import LearningsStore
from agendum.store.memory_store import MemoryStore
from agendum.store.project_store import ProjectStore
from agendum.store.trace_store import TraceStore
from agendum.tools import register


class _Stores:
    """Lazy-initialized stores — resolve root at first access."""

    def __init__(self) -> None:
        self._root: Path | None = None
        self._board: BoardStore | None = None
        self._project: ProjectStore | None = None
        self._memory: MemoryStore | None = None
        self._trace: TraceStore | None = None
        self._learnings: LearningsStore | None = None

    @property
    def root(self) -> Path:
        if self._root is None:
            self._root = resolve_root()
        return self._root

    @property
    def board(self) -> BoardStore:
        if self._board is None:
            self._board = BoardStore(self.root)
        return self._board

    @property
    def project(self) -> ProjectStore:
        if self._project is None:
            self._project = ProjectStore(self.root)
        return self._project

    @property
    def memory(self) -> MemoryStore:
        if self._memory is None:
            self._memory = MemoryStore(self.root)
        return self._memory

    @property
    def trace(self) -> TraceStore:
        if self._trace is None:
            self._trace = TraceStore(self.root)
        return self._trace

    @property
    def learnings(self) -> LearningsStore:
        if self._learnings is None:
            self._learnings = LearningsStore(self.root)
        return self._learnings


stores = _Stores()


class _LazyEnricher:
    """Defers enrichment source registration until first use."""

    def __init__(self) -> None:
        self._inner: ContextEnricher | None = None

    def _init(self) -> ContextEnricher:
        if self._inner is None:
            self._inner = ContextEnricher()
            self._inner.register(ProjectRulesSource(stores.root))
            self._inner.register(MemorySource(stores.memory))
            self._inner.register(DependencySource(stores.board))
        return self._inner

    def enrich(self, *args, **kwargs):
        return self._init().enrich(*args, **kwargs)


enricher = _LazyEnricher()

INSTRUCTIONS = """agendum is a project memory and scoping engine for AI coding agents.
Use pm_* tools to manage projects, board items, memory, and work packages.
Start with pm_init to initialize, then pm_project to create a project.
Use pm_status to see an overview. Use pm_add to add items to the board.
Use pm_ingest to import a plan file. Use pm_next to get scoped work packages.
Use pm_done to report completion. Use pm_learn for cross-project learnings."""

mcp = FastMCP("agendum", instructions=INSTRUCTIONS)
register(mcp, stores, enricher)
```

- [ ] **Step 2: Delete old tool modules**

Delete the entire `src/agendum/tools/` directory and old store files:

```bash
rm -rf src/agendum/tools/
rm -f src/agendum/store/agent_store.py
rm -f src/agendum/store/plan_store.py
rm -f src/agendum/store/task_store.py
rm -f src/agendum/store/task_format.py
```

- [ ] **Step 3: Delete old test files**

```bash
rm -f tests/test_mcp_agent.py tests/test_mcp_board.py tests/test_mcp_task.py
rm -f tests/test_mcp_task_workflow.py tests/test_mcp_utils.py
rm -f tests/test_orch_approve.py tests/test_orch_dispatch.py tests/test_orch_flow.py
rm -f tests/test_orch_plan.py tests/test_orch_review.py tests/test_model_routing.py
rm -f tests/test_task_store.py tests/test_plan_store.py
rm -f tests/test_enrichment_core.py tests/test_enrichment_sources.py
```

- [ ] **Step 4: Update conftest.py — remove old fixtures**

Remove the `mcp_server` fixture, `setup` fixture, `_tasks_json`, `_create_and_approve` helpers. Keep `tmp_root`, `call()`, and `v2_server`.

Update imports — remove all old tool module imports and orchestrator references.

- [ ] **Step 5: Fix remaining tests that reference old imports**

Update tests that we're keeping:
- `test_topological.py` — should work as-is (uses `task_graph.py`)
- `test_complexity.py` — should work as-is
- `test_memory_store.py` — should work (MemoryStore unchanged except new scope)
- `test_project_store.py` — update to remove policy-related tests
- `test_trace_store.py` — should work as-is
- `test_concurrent.py` — update to use BoardStore instead of TaskStore
- `test_deps.py` — update if it references old models
- `test_load.py` — update for new server imports
- `test_security.py` — should work as-is
- `test_mcp_project.py` — update to use `pm_project` tool with action parameter
- `test_mcp_memory.py` — update to use `pm_memory` tool with action parameter

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 7: Run ruff**

Run: `uv run ruff check src/ tests/`
Expected: Clean

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: rewire server.py, delete old tools/stores/tests for v2"
```

---

### Task 6: Adapt remaining tests and ensure full coverage

**Files:**
- Modify: `tests/test_concurrent.py`
- Modify: `tests/test_mcp_project.py`
- Modify: `tests/test_mcp_memory.py`
- Modify: `tests/test_project_store.py`
- Modify: `tests/test_load.py`
- Modify: `tests/test_deps.py`

- [ ] **Step 1: Fix test_concurrent.py**

Change `TaskStore` references to `BoardStore`, `create_task` to `create_item`, `task-` prefix expectations to `item-`.

- [ ] **Step 2: Fix test_mcp_project.py**

Update tool calls from `pm_project_create` → `pm_project(action="create", ...)`, etc.

- [ ] **Step 3: Fix test_mcp_memory.py**

Update tool calls from `pm_memory_read` → `pm_memory(action="read", ...)`, etc.

- [ ] **Step 4: Fix test_project_store.py**

Remove tests for `get_policy`, `update_policy`. Update directory expectations from `tasks/` to `board/`.

- [ ] **Step 5: Fix test_load.py**

Update import to test that `from agendum.server import mcp` works.

- [ ] **Step 6: Fix test_deps.py**

Update any references to old models/stores.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 8: Run ruff and format**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check .`
Expected: Clean

- [ ] **Step 9: Commit**

```bash
git add tests/
git commit -m "test: adapt remaining tests for v2 architecture"
```

---

### Task 7: Update documentation — CLAUDE.md, README.md, cleanup

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `AGENTS.md` (if it exists)
- Modify: `src/agendum/cli.py` (remove agent-related commands if any)
- Delete: any remaining dead code

- [ ] **Step 1: Rewrite CLAUDE.md**

```markdown
# agendum

Project memory and scoping engine for AI coding agents. Python 3.13+, uv, FastMCP.

## Workflow

agendum augments the harness (Claude Code + superpowers + plan mode). It does NOT compete with it.

### Separation of concerns

| Concern | Owner |
|---------|-------|
| Brainstorming & design | Superpowers (brainstorming skill) |
| Planning & task breakdown | Superpowers (writing-plans) + plan mode |
| Subagent dispatch | Claude Code Agent tool |
| **Persistent project state** | **agendum** |
| **Bounded work packages** | **agendum** |
| **Cross-session memory** | **agendum** |
| **Project board / backlog** | **agendum** |

### The flow

```
1. PLAN (harness)    brainstorming → writing-plans → plan file
2. INGEST (agendum)  pm_ingest reads plan → creates bounded board items
3. SCOPE (agendum)   pm_next returns scoped work package with context
4. EXECUTE (harness)  Agent works within the scoped package
5. REPORT (agendum)  pm_done records completion, decisions, patterns
6. RESUME (agendum)  Next session: pm_status → pm_next → continue
```

### When to skip agendum

- Single-line fixes (typos, version bumps)
- Pure research/exploration (no code changes)

## Quick reference

```bash
uv run pytest               # all tests must pass
uv run ruff check src/ tests/  # lint
uv run ruff format .        # format
```

## Architecture

- **11 MCP tools** in `tools.py`
- **4 stores**: BoardStore, ProjectStore, MemoryStore, LearningsStore
- **Enrichment pipeline**: `enrichment/pipeline.py` + `enrichment/sources.py`
- All writes use `get_lock()` + `atomic_write()` from `store/locking.py`
- Board items: Markdown + YAML frontmatter in `.agendum/projects/<project>/board/`
- Global learnings: `.agendum/learnings/`
- Memory: `.agendum/memory/`

## Conventions

- MCP tools: `pm_<name>` (e.g., `pm_add`, `pm_next`, `pm_done`)
- Store methods: lowercase verb (`create_item`, `get_item`, `list_items`)
- Tests: `test_<module>.py`
- MCP tools return error strings, never raise exceptions
- No Co-Authored-By lines in commits
- Line length: 120 chars
```

- [ ] **Step 2: Update README.md**

Update the tool list, architecture description, and examples to reflect the 11-tool v2 surface. Update the "Why agendum?" section to emphasize Project Memory + Scoping Engine positioning.

- [ ] **Step 3: Update cli.py if needed**

Remove any agent-related CLI commands. Keep `serve` command.

- [ ] **Step 4: Final cleanup — remove any dead imports or files**

Scan for any remaining references to old modules:

```bash
uv run ruff check src/ tests/
grep -r "task_store\|agent_store\|plan_store\|task_format\|orchestrator\|AgentStore\|PlanStore\|TaskStore" src/ tests/ --include="*.py"
```

Fix any remaining references.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 6: Run ruff check and format**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check .`
Expected: Clean

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "docs: update CLAUDE.md and README.md for v2 architecture"
```

- [ ] **Step 8: Update home CLAUDE.md workflow reference**

Update `/home/shivam/CLAUDE.md` to reflect the new agendum v2 workflow (the section about agendum task management).

- [ ] **Step 9: Final verification**

```bash
cd /home/shivam/Projects/agendum
uv run pytest -v
uv run ruff check src/ tests/
uv run ruff format --check .
```

All must pass.
