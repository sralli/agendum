"""Trace store: append-only execution traces for task attempts."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from agendum.models import ExecutionTrace
from agendum.store import sanitize_name
from agendum.store.locking import atomic_write, get_lock

logger = logging.getLogger(__name__)


class TraceStore:
    """Append-only trace storage backed by .agendum/traces/."""

    def __init__(self, root: Path):
        self.root = root

    def _traces_dir(self, project: str) -> Path:
        return self.root / "traces" / sanitize_name(project)

    def write_trace(self, trace: ExecutionTrace) -> Path:
        """Write a trace file. Never overwrites — each attempt gets a unique file."""
        traces_dir = self._traces_dir(trace.project)
        traces_dir.mkdir(parents=True, exist_ok=True)

        ts = trace.started.strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"{sanitize_name(trace.task_id)}-{ts}.yaml"
        path = traces_dir / filename

        # Handle potential collision by appending a counter
        counter = 0
        while path.exists():
            counter += 1
            filename = f"{sanitize_name(trace.task_id)}-{ts}-{counter}.yaml"
            path = traces_dir / filename

        data = trace.model_dump(mode="json", exclude_none=True)
        with get_lock(path):
            atomic_write(path, yaml.dump(data, default_flow_style=False, sort_keys=False))
        return path

    def list_traces(
        self,
        project: str,
        plan_id: str | None = None,
        task_id: str | None = None,
    ) -> list[ExecutionTrace]:
        """List traces with optional filters."""
        traces_dir = self._traces_dir(project)
        if not traces_dir.exists():
            return []

        traces = []
        for path in sorted(traces_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                trace = ExecutionTrace.model_validate(data)
                if plan_id and trace.plan_id != plan_id:
                    continue
                if task_id and trace.task_id != task_id:
                    continue
                traces.append(trace)
            except Exception:
                logger.warning("Failed to parse trace file: %s", path)
                continue
        return traces
