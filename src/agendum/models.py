"""Pydantic models for agendum."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# --- Enums ---


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskType(StrEnum):
    DEV = "dev"
    DOCS = "docs"
    EMAIL = "email"
    PLANNING = "planning"
    PERSONAL = "personal"
    OPS = "ops"
    RESEARCH = "research"
    REVIEW = "review"


# --- Core Models ---


class ProgressEntry(BaseModel):
    """A single entry in a task's progress log."""

    timestamp: datetime
    agent: str
    message: str


class MemoryEntry(BaseModel):
    """A single memory entry."""

    key: str
    scope: str  # project, decisions, patterns
    content: str
    tags: list[str] = Field(default_factory=list)
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BoardConfig(BaseModel):
    """Board configuration stored in config.yaml."""

    version: str = "1"
    name: str = "agendum"
    projects: list[str] = Field(default_factory=list)
    default_project: str | None = None


class Project(BaseModel):
    """A project containing tasks and a spec."""

    name: str
    description: str = ""
    spec: str = ""  # Markdown content of spec.md
    plan: str = ""  # Markdown content of plan.md
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- v2 Models ---


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
    verified: bool = False


# Type alias: task_graph.py uses Task, which is now BoardItem
Task = BoardItem


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
    complexity: str = ""  # trivial, small, medium, large
    estimated_scope: str = ""  # human-readable one-liner
