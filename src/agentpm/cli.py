"""agentpm CLI — human interface for project management."""

from __future__ import annotations

from pathlib import Path

import click

from agentpm.deps import suggest_next_task
from agentpm.models import TaskStatus
from agentpm.store.project_store import ProjectStore
from agentpm.store.task_store import TaskStore


def _get_root(home: bool = False) -> Path:
    if home:
        return Path.home() / ".agentpm"
    return Path.cwd() / ".agentpm"


@click.group()
@click.option("--home", is_flag=True, help="Use ~/.agentpm instead of ./.agentpm")
@click.pass_context
def cli(ctx: click.Context, home: bool) -> None:
    """agentpm — Universal project management for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["root"] = _get_root(home)


@cli.command()
@click.argument("name", default="agentpm")
@click.pass_context
def init(ctx: click.Context, name: str) -> None:
    """Initialize .agentpm/ directory."""
    root = ctx.obj["root"]
    store = ProjectStore(root)
    store.init_board(name)
    click.echo(f"Initialized agentpm at {root}")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show board overview."""
    root = ctx.obj["root"]
    project_store = ProjectStore(root)
    task_store = TaskStore(root)

    projects = project_store.list_projects()
    if not projects:
        click.echo("No projects. Run: agentpm init && agentpm project create <name>")
        return

    for proj in projects:
        tasks = task_store.list_tasks(proj)
        by_status: dict[str, int] = {}
        for t in tasks:
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

        click.echo(f"\n📋 {proj} ({len(tasks)} tasks)")
        for s, count in sorted(by_status.items()):
            click.echo(f"  {s}: {count}")


@cli.group()
def project() -> None:
    """Manage projects."""
    pass


@project.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Project description")
@click.pass_context
def project_create(ctx: click.Context, name: str, description: str) -> None:
    """Create a new project."""
    root = ctx.obj["root"]
    store = ProjectStore(root)
    store.create_project(name, description)
    click.echo(f"Created project '{name}'")


@project.command("list")
@click.pass_context
def project_list(ctx: click.Context) -> None:
    """List all projects."""
    root = ctx.obj["root"]
    store = ProjectStore(root)
    for p in store.list_projects():
        click.echo(f"  - {p}")


@cli.group()
def task() -> None:
    """Manage tasks."""
    pass


@task.command("create")
@click.argument("project")
@click.argument("title")
@click.option("--priority", "-p", default="medium")
@click.option("--type", "task_type", default="dev")
@click.option("--depends", "-d", multiple=True, help="Task IDs this depends on")
@click.pass_context
def task_create(
    ctx: click.Context, project: str, title: str, priority: str, task_type: str, depends: tuple[str, ...]
) -> None:
    """Create a new task."""
    root = ctx.obj["root"]
    store = TaskStore(root)
    t = store.create_task(
        project=project,
        title=title,
        priority=priority,
        type=task_type,
        depends_on=list(depends),
    )
    click.echo(f"Created {t.id}: {t.title}")


@task.command("list")
@click.argument("project")
@click.option("--status", "-s", default=None)
@click.pass_context
def task_list(ctx: click.Context, project: str, status: str | None) -> None:
    """List tasks in a project."""
    root = ctx.obj["root"]
    store = TaskStore(root)
    status_enum = TaskStatus(status) if status else None
    tasks = store.list_tasks(project, status=status_enum)

    for t in tasks:
        assigned = f" [{t.assigned}]" if t.assigned else ""
        click.echo(f"  [{t.status.value:^11}] {t.id}: {t.title} ({t.priority.value}){assigned}")


@cli.command()
@click.argument("project")
@click.pass_context
def next(ctx: click.Context, project: str) -> None:
    """Suggest the next task to work on."""
    root = ctx.obj["root"]
    store = TaskStore(root)
    tasks = store.list_tasks(project)
    task = suggest_next_task(tasks)

    if not task:
        click.echo("No tasks available.")
        return

    click.echo(f"Next: {task.id}: {task.title} ({task.priority.value})")
    if task.context:
        click.echo(f"  Context: {task.context[:200]}")


@cli.command()
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start the MCP server (stdio transport)."""
    import os

    # Set root for server
    os.environ["AGENTPM_ROOT"] = str(ctx.obj["root"])

    from agentpm.server import mcp
    mcp.run(transport="stdio")


if __name__ == "__main__":
    cli()
