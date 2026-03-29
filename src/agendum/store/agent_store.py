"""Agent persistence store: read/write agent records to .agendum/agents/."""

from __future__ import annotations

from pathlib import Path

from agendum.models import AgentPersistenceRecord
from agendum.store import sanitize_name
from agendum.store.locking import atomic_write, get_lock


class AgentStore:
    """Disk-backed agent registry for cross-session visibility."""

    def __init__(self, root: Path):
        self.root = root
        self.agents_dir = root / "agents"

    def ensure_dir(self) -> None:
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def _agent_path(self, agent_id: str) -> Path:
        return self.agents_dir / f"{sanitize_name(agent_id)}.json"

    def save(self, record: AgentPersistenceRecord) -> None:
        """Persist an agent record to disk (locked + atomic)."""
        self.ensure_dir()
        path = self._agent_path(record.id)
        with get_lock(path):
            atomic_write(path, record.model_dump_json(indent=2))

    def load(self, agent_id: str) -> AgentPersistenceRecord | None:
        """Load an agent record from disk, or None if not found."""
        path = self._agent_path(agent_id)
        if not path.exists():
            return None
        try:
            return AgentPersistenceRecord.model_validate_json(path.read_text())
        except Exception:
            return None

    def list_agents(self) -> list[AgentPersistenceRecord]:
        """List all persisted agent records."""
        if not self.agents_dir.exists():
            return []
        records = []
        for p in sorted(self.agents_dir.glob("*.json")):
            try:
                records.append(AgentPersistenceRecord.model_validate_json(p.read_text()))
            except Exception:
                continue
        return records
