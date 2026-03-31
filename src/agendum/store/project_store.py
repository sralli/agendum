"""Project store: manage project specs, plans, and config."""

from __future__ import annotations

from pathlib import Path

import yaml

from agendum.models import BoardConfig, Project
from agendum.store import sanitize_name
from agendum.store.locking import atomic_write, get_lock


class ProjectStore:
    """File-based project and config storage."""

    def __init__(self, root: Path):
        self.root = root

    def _project_dir(self, project: str) -> Path:
        return self.root / "projects" / sanitize_name(project)

    def init_board(self, name: str = "agendum") -> BoardConfig:
        """Initialize .agendum/ directory structure."""
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "projects").mkdir(exist_ok=True)
        (self.root / "learnings").mkdir(exist_ok=True)
        (self.root / "memory").mkdir(exist_ok=True)

        config = BoardConfig(name=name)
        self._write_config(config)
        return config

    def _config_path(self) -> Path:
        return self.root / "config.yaml"

    def _write_config(self, config: BoardConfig) -> None:
        path = self._config_path()
        with get_lock(path):
            atomic_write(path, yaml.dump(config.model_dump(), default_flow_style=False, sort_keys=False))

    def read_config(self) -> BoardConfig:
        path = self._config_path()
        if not path.exists():
            return BoardConfig()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return BoardConfig(**data)

    def create_project(self, name: str, description: str = "") -> Project:
        """Create a new project with directory structure."""
        name = sanitize_name(name)
        project_dir = self._project_dir(name)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "board").mkdir(exist_ok=True)

        project = Project(name=name, description=description)

        # Write spec.md
        spec_content = f"# {name}\n\n{description}\n\n## Requirements\n\n## Design\n"
        (project_dir / "spec.md").write_text(spec_content)

        # Write plan.md
        plan_content = f"# {name} — Plan\n\n## Tasks\n\n_No tasks yet._\n"
        (project_dir / "plan.md").write_text(plan_content)

        # Update config
        config = self.read_config()
        if name not in config.projects:
            config.projects.append(name)
            if config.default_project is None:
                config.default_project = name
            self._write_config(config)

        return project

    def get_project(self, name: str) -> Project | None:
        name = sanitize_name(name)
        project_dir = self._project_dir(name)
        if not project_dir.exists():
            return None

        spec = ""
        spec_path = project_dir / "spec.md"
        if spec_path.exists():
            spec = spec_path.read_text(encoding="utf-8")

        plan = ""
        plan_path = project_dir / "plan.md"
        if plan_path.exists():
            plan = plan_path.read_text(encoding="utf-8")

        return Project(name=name, spec=spec, plan=plan)

    def update_spec(self, project: str, content: str) -> None:
        project = sanitize_name(project)
        project_dir = self._project_dir(project)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{project}' does not exist")
        path = project_dir / "spec.md"
        with get_lock(path):
            atomic_write(path, content)

    def update_plan(self, project: str, content: str) -> None:
        project = sanitize_name(project)
        project_dir = self._project_dir(project)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{project}' does not exist")
        path = project_dir / "plan.md"
        with get_lock(path):
            atomic_write(path, content)

    def list_projects(self) -> list[str]:
        projects_dir = self.root / "projects"
        if not projects_dir.exists():
            return []
        return sorted(d.name for d in projects_dir.iterdir() if d.is_dir())

