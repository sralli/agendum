"""Pydantic models for agentpm."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


# --- Enums ---


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskType(str, Enum):
    DEV = "dev"
    DOCS = "docs"
    EMAIL = "email"
    PLANNING = "planning"
    PERSONAL = "personal"
    OPS = "ops"
    RESEARCH = "research"
    REVIEW = "review"


class TaskCategory(str, Enum):
    CODE_COMPLEX = "code-complex"
    CODE_SIMPLE = "code-simple"
    CODE_FRONTEND = "code-frontend"
    PLANNING = "planning"
    REVIEW = "review"
    DOCS = "docs"
    EMAIL = "email"
    RESEARCH = "research"
    PERSONAL = "personal"


# --- Core Models ---


class Task(BaseModel):
    """A single task in the project board."""

    id: str
    project: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    type: TaskType = TaskType.DEV
    category: TaskCategory | None = None
    assigned: str | None = None
    created_by: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Body sections (Markdown content, not in frontmatter)
    context: str = ""
    progress: list[ProgressEntry] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    handoff: str = ""


class ProgressEntry(BaseModel):
    """A single entry in a task's progress log."""

    timestamp: datetime
    agent: str
    message: str


class Project(BaseModel):
    """A project containing tasks and a spec."""

    name: str
    description: str = ""
    spec: str = ""  # Markdown content of spec.md
    plan: str = ""  # Markdown content of plan.md
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Agent(BaseModel):
    """A registered agent identity."""

    id: str
    type: str  # claude-code, cursor, opencode, human
    capabilities: list[str] = Field(default_factory=list)
    model: str | None = None
    started: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"  # active, idle, disconnected
    current_task: str | None = None


class MemoryEntry(BaseModel):
    """A single memory entry."""

    key: str
    scope: str  # project, decisions, patterns
    content: str
    tags: list[str] = Field(default_factory=list)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BoardConfig(BaseModel):
    """Board configuration stored in config.yaml."""

    version: str = "1"
    name: str = "agentpm"
    projects: list[str] = Field(default_factory=list)
    default_project: str | None = None
    agent_routing: dict[str, str] = Field(default_factory=dict)


class BoardStatus(BaseModel):
    """Overview of board state."""

    projects: list[str]
    total_tasks: int
    by_status: dict[str, int]
    blocked_tasks: list[str]
    active_agents: list[str]
    recent_activity: list[str]


# Forward ref update
Task.model_rebuild()
