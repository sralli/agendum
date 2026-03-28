"""Project store: manage project specs, plans, and config."""

from __future__ import annotations

from pathlib import Path

import yaml

from agentpm.models import BoardConfig, Project
from agentpm.store.task_store import _sanitize_name


class ProjectStore:
    """File-based project and config storage."""

    def __init__(self, root: Path):
        self.root = root

    def init_board(self, name: str = "agentpm") -> BoardConfig:
        """Initialize .agentpm/ directory structure."""
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "projects").mkdir(exist_ok=True)
        (self.root / "agents").mkdir(exist_ok=True)
        (self.root / "memory").mkdir(exist_ok=True)

        config = BoardConfig(name=name)
        self._write_config(config)
        return config

    def _config_path(self) -> Path:
        return self.root / "config.yaml"

    def _write_config(self, config: BoardConfig) -> None:
        self._config_path().write_text(
            yaml.dump(config.model_dump(), default_flow_style=False, sort_keys=False)
        )

    def read_config(self) -> BoardConfig:
        path = self._config_path()
        if not path.exists():
            return BoardConfig()
        data = yaml.safe_load(path.read_text()) or {}
        return BoardConfig(**data)

    def create_project(self, name: str, description: str = "") -> Project:
        """Create a new project with directory structure."""
        name = _sanitize_name(name)
        project_dir = self.root / "projects" / name
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "tasks").mkdir(exist_ok=True)

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
        name = _sanitize_name(name)
        project_dir = self.root / "projects" / name
        if not project_dir.exists():
            return None

        spec = ""
        spec_path = project_dir / "spec.md"
        if spec_path.exists():
            spec = spec_path.read_text()

        plan = ""
        plan_path = project_dir / "plan.md"
        if plan_path.exists():
            plan = plan_path.read_text()

        return Project(name=name, spec=spec, plan=plan)

    def update_spec(self, project: str, content: str) -> None:
        project = _sanitize_name(project)
        project_dir = self.root / "projects" / project
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{project}' does not exist")
        (project_dir / "spec.md").write_text(content)

    def update_plan(self, project: str, content: str) -> None:
        project = _sanitize_name(project)
        project_dir = self.root / "projects" / project
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{project}' does not exist")
        (project_dir / "plan.md").write_text(content)

    def list_projects(self) -> list[str]:
        projects_dir = self.root / "projects"
        if not projects_dir.exists():
            return []
        return sorted(d.name for d in projects_dir.iterdir() if d.is_dir())
