"""Pydantic models for agendum."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

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


class TaskCategory(StrEnum):
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


class AgentHandoffRecord(BaseModel):
    """Structured snapshot left by an agent when handing off a task."""

    agent_id: str
    agent_type: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    device: str | None = None
    git_branch: str | None = None
    working_dir: str | None = None
    completed: list[str] = Field(default_factory=list)
    remaining: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    gotchas: list[str] = Field(default_factory=list)
    next_agent_hints: dict[str, Any] = Field(default_factory=dict)


class AgentPersistenceRecord(BaseModel):
    """Disk-backed agent record for cross-session visibility."""

    id: str
    type: str
    capabilities: list[str] = Field(default_factory=list)
    model: str | None = None
    started: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_task: str | None = None
    session_count: int = 1


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
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Body sections (Markdown content, not in frontmatter)
    context: str = ""
    progress: list[ProgressEntry] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    handoff: str = ""  # legacy free-text handoff (kept for backward compat)
    structured_handoff: AgentHandoffRecord | None = None
    agent_history: list[AgentHandoffRecord] = Field(default_factory=list)


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
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Agent(BaseModel):
    """A registered agent identity."""

    id: str
    type: str  # claude-code, cursor, opencode, human
    capabilities: list[str] = Field(default_factory=list)
    model: str | None = None
    started: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "active"  # active, idle, disconnected
    current_task: str | None = None


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
    agent_routing: dict[str, str] = Field(default_factory=dict)


class BoardStatus(BaseModel):
    """Overview of board state."""

    projects: list[str]
    total_tasks: int
    by_status: dict[str, int]
    blocked_tasks: list[str]
    active_agents: list[str]
    recent_activity: list[str]


# --- Orchestrator Models (Phase 2) ---


class ExecutionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalPolicy(StrEnum):
    HUMAN_REQUIRED = "human_required"
    AUTO_WITH_REVIEW = "auto_with_review"
    AUTO = "auto"


class TaskCompletionStatus(StrEnum):
    DONE = "done"
    DONE_WITH_CONCERNS = "done_with_concerns"
    NEEDS_CONTEXT = "needs_context"
    BLOCKED = "blocked"


class ExecutionLevel(BaseModel):
    """A group of tasks at the same dependency depth, executable in parallel."""

    level: int
    task_ids: list[str]
    is_checkpoint: bool = False


class ContextPacket(BaseModel):
    """Constructed context for a sub-agent executing a task."""

    task_id: str
    goal: str = ""
    spec_excerpt: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    dependencies_summary: str = ""
    constraints: list[str] = Field(default_factory=list)
    review_checklist: list[str] = Field(default_factory=list)

    # Enrichment fields (populated at dispatch time, empty at plan creation)
    project_rules: str = ""
    memory_context: str = ""
    dependency_outputs: str = ""
    review_history: str = ""
    pointers: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    """A structured execution plan with DAG levels and context packets."""

    id: str
    project: str
    goal: str
    status: ExecutionStatus = ExecutionStatus.DRAFT
    approval_policy: ApprovalPolicy = ApprovalPolicy.AUTO_WITH_REVIEW
    task_ids: list[str] = Field(default_factory=list)
    levels: list[ExecutionLevel] = Field(default_factory=list)
    context_packets: dict[str, ContextPacket] = Field(default_factory=dict)
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "unknown"
    revision: int = 1


class ExecutionTrace(BaseModel):
    """Append-only record of a single task execution attempt."""

    task_id: str
    plan_id: str | None = None
    project: str
    agent_id: str
    agent_type: str | None = None
    model: str | None = None

    # Timing
    started: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed: datetime | None = None
    duration_seconds: float | None = None

    # Outcome
    completion_status: TaskCompletionStatus | None = None
    concerns: list[str] = Field(default_factory=list)
    context_needed: list[str] = Field(default_factory=list)
    block_reason: str | None = None

    # Metrics
    attempts: int = 1
    files_changed: list[str] = Field(default_factory=list)
    review_cycles: int = 0
    review_issues: list[str] = Field(default_factory=list)

    # Task metadata (denormalized for aggregation)
    task_type: str | None = None
    task_category: str | None = None
    task_priority: str | None = None


class ExternalReference(BaseModel):
    """A pointer to an external resource (Obsidian note, wiki URL, etc.)."""

    name: str
    path_or_url: str


class ProjectPolicy(BaseModel):
    """Per-project orchestration policy."""

    approval_policy: ApprovalPolicy = ApprovalPolicy.AUTO_WITH_REVIEW
    review_required: bool = False
    checkpoint_interval: int = 0
    max_parallel_tasks: int = 5
    max_context_chars: int = 8000
    disabled_sources: list[str] = Field(default_factory=list)
    external_references: list[ExternalReference] = Field(default_factory=list)


# Forward ref update
Task.model_rebuild()
