"""Tests for concrete context enrichment sources."""

from __future__ import annotations

from datetime import UTC, datetime

from agendum.models import (
    AgentHandoffRecord,
    ContextPacket,
    ExternalReference,
    ProgressEntry,
    Task,
    TaskStatus,
)
from agendum.store.memory_store import MemoryStore
from agendum.store.project_store import ProjectStore
from agendum.store.task_store import TaskStore
from agendum.tools.orchestrator.sources import (
    ExternalReferencesSource,
    HandoffSource,
    MemorySource,
    ProjectRulesSource,
    ReviewHistorySource,
)


def _packet(task_id: str = "task-001", goal: str = "Test goal") -> ContextPacket:
    return ContextPacket(task_id=task_id, goal=goal)


def _task(task_id: str = "task-001", title: str = "Test task") -> Task:
    return Task(id=task_id, project="test", title=title, status=TaskStatus.PENDING)


class TestProjectRulesSource:
    def test_loads_claude_md(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "CLAUDE.md").write_text("# Project Rules\nUse ruff. Line length 120.")
        agendum_root = tmp_path / ".agendum"
        agendum_root.mkdir()

        source = ProjectRulesSource(agendum_root)
        result = source.enrich(_packet(), _task(), "test")
        assert "Project Rules" in result.project_rules
        assert any("CLAUDE.md" in p for p in result.pointers)

    def test_prefers_claude_md_over_agents_md(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "CLAUDE.md").write_text("CLAUDE content")
        (tmp_path / "AGENTS.md").write_text("AGENTS content")
        agendum_root = tmp_path / ".agendum"
        agendum_root.mkdir()

        source = ProjectRulesSource(agendum_root)
        result = source.enrich(_packet(), _task(), "test")
        assert "CLAUDE content" in result.project_rules

    def test_falls_back_to_agents_md(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "AGENTS.md").write_text("AGENTS content")
        agendum_root = tmp_path / ".agendum"
        agendum_root.mkdir()

        source = ProjectRulesSource(agendum_root)
        result = source.enrich(_packet(), _task(), "test")
        assert "AGENTS content" in result.project_rules

    def test_no_git_root(self, tmp_path):
        agendum_root = tmp_path / ".agendum"
        agendum_root.mkdir()

        source = ProjectRulesSource(agendum_root)
        result = source.enrich(_packet(), _task(), "test")
        assert result.project_rules == ""

    def test_no_rule_files(self, tmp_path):
        (tmp_path / ".git").mkdir()
        agendum_root = tmp_path / ".agendum"
        agendum_root.mkdir()

        source = ProjectRulesSource(agendum_root)
        result = source.enrich(_packet(), _task(), "test")
        assert result.project_rules == ""

    def test_truncation(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "CLAUDE.md").write_text("x" * 5000)
        agendum_root = tmp_path / ".agendum"
        agendum_root.mkdir()

        source = ProjectRulesSource(agendum_root, max_chars=100)
        result = source.enrich(_packet(), _task(), "test")
        assert len(result.project_rules) == 100


class TestMemorySource:
    def test_search_finds_matches(self, tmp_path):
        root = tmp_path / ".agendum"
        root.mkdir()
        store = MemoryStore(root)
        store.write("decisions", "- Use JWT for auth tokens\n- Use bcrypt for passwords\n")

        source = MemorySource(store)
        packet = _packet(goal="auth tokens")
        result = source.enrich(packet, _task(), "test")
        assert "JWT" in result.memory_context
        assert any("decisions" in p for p in result.pointers)

    def test_no_matches(self, tmp_path):
        root = tmp_path / ".agendum"
        root.mkdir()
        store = MemoryStore(root)

        source = MemorySource(store)
        result = source.enrich(_packet(goal="nothing relevant"), _task(), "test")
        assert result.memory_context == ""

    def test_empty_goal(self, tmp_path):
        root = tmp_path / ".agendum"
        root.mkdir()
        store = MemoryStore(root)

        source = MemorySource(store)
        result = source.enrich(_packet(goal=""), _task(title=""), "test")
        assert result.memory_context == ""


class TestHandoffSource:
    def test_loads_dependency_handoffs(self, tmp_path):
        root = tmp_path / ".agendum"
        root.mkdir()
        store = TaskStore(root)
        store.ensure_project("test")

        dep = store.create_task("test", "Setup DB")
        store.update_task(
            "test",
            dep.id,
            status=TaskStatus.DONE,
            structured_handoff=AgentHandoffRecord(
                agent_id="claude",
                completed=["Schema created", "Migrations run"],
                gotchas=["Postgres 16 required"],
                decisions=["Use UUID primary keys"],
            ),
        )

        task = _task()
        task.depends_on = [dep.id]

        source = HandoffSource(store)
        result = source.enrich(_packet(), task, "test")
        assert "Schema created" in result.dependency_outputs
        assert "Postgres 16" in result.dependency_outputs
        assert any(dep.id in p for p in result.pointers)

    def test_no_dependencies(self, tmp_path):
        root = tmp_path / ".agendum"
        root.mkdir()
        store = TaskStore(root)

        source = HandoffSource(store)
        result = source.enrich(_packet(), _task(), "test")
        assert result.dependency_outputs == ""

    def test_dep_not_done(self, tmp_path):
        root = tmp_path / ".agendum"
        root.mkdir()
        store = TaskStore(root)
        store.ensure_project("test")
        dep = store.create_task("test", "Pending task")

        task = _task()
        task.depends_on = [dep.id]

        source = HandoffSource(store)
        result = source.enrich(_packet(), task, "test")
        assert result.dependency_outputs == ""


class TestReviewHistorySource:
    def test_extracts_review_failures(self):
        task = _task()
        task.progress = [
            ProgressEntry(
                timestamp=datetime(2026, 3, 29, tzinfo=UTC),
                agent="reviewer",
                message="Review FAILED (spec): Missing error handling",
            ),
            ProgressEntry(
                timestamp=datetime(2026, 3, 29, 1, tzinfo=UTC),
                agent="dev",
                message="Fixed error handling",
            ),
        ]

        source = ReviewHistorySource()
        result = source.enrich(_packet(), task, "test")
        assert "Review FAILED" in result.review_history
        assert "Missing error handling" in result.review_history
        assert "Fixed error handling" not in result.review_history

    def test_no_failures(self):
        task = _task()
        task.progress = [
            ProgressEntry(
                timestamp=datetime(2026, 3, 29, tzinfo=UTC),
                agent="dev",
                message="Task completed successfully",
            ),
        ]

        source = ReviewHistorySource()
        result = source.enrich(_packet(), task, "test")
        assert result.review_history == ""

    def test_empty_progress(self):
        source = ReviewHistorySource()
        result = source.enrich(_packet(), _task(), "test")
        assert result.review_history == ""

    def test_extracts_criteria_failures(self):
        """ReviewHistorySource extracts structured criteria failure details."""
        task = _task()
        task.progress = [
            ProgressEntry(
                timestamp=datetime(2026, 3, 29, tzinfo=UTC),
                agent="reviewer",
                message="Review FAILED (spec): Criterion failed: Login works",
            ),
            ProgressEntry(
                timestamp=datetime(2026, 3, 29, 1, tzinfo=UTC),
                agent="reviewer",
                message="Criteria failed: Login works, Logout works",
            ),
        ]

        source = ReviewHistorySource()
        result = source.enrich(_packet(), task, "test")
        assert "Review FAILED" in result.review_history
        assert "Login works" in result.review_history
        assert "Logout works" in result.review_history
        assert "Prior review failures:" in result.review_history
        assert "Criteria that failed:" in result.review_history

    def test_criteria_failed_only(self):
        """ReviewHistorySource handles entries with only Criteria failed (no Review FAILED)."""
        task = _task()
        task.progress = [
            ProgressEntry(
                timestamp=datetime(2026, 3, 29, tzinfo=UTC),
                agent="reviewer",
                message="Criteria failed: Signup flow, Email validation",
            ),
        ]

        source = ReviewHistorySource()
        result = source.enrich(_packet(), task, "test")
        assert "Signup flow" in result.review_history
        assert "Email validation" in result.review_history
        assert "Prior review failures:" not in result.review_history
        assert "Criteria that failed:" in result.review_history


class TestExternalReferencesSource:
    def test_adds_pointers(self, tmp_path):
        root = tmp_path / ".agendum"
        root.mkdir()
        store = ProjectStore(root)
        store.create_project("test")
        store.update_policy(
            "test",
            external_references=[
                ExternalReference(name="Obsidian", path_or_url="/home/user/Vault/auth.md"),
                ExternalReference(name="Wiki", path_or_url="https://wiki.example.com/auth"),
            ],
        )

        source = ExternalReferencesSource(store)
        result = source.enrich(_packet(), _task(), "test")
        assert any("Obsidian" in p for p in result.pointers)
        assert any("wiki.example.com" in p for p in result.pointers)

    def test_no_references(self, tmp_path):
        root = tmp_path / ".agendum"
        root.mkdir()
        store = ProjectStore(root)
        store.create_project("test")

        source = ExternalReferencesSource(store)
        result = source.enrich(_packet(), _task(), "test")
        assert result.pointers == []
