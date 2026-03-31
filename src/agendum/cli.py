"""agendum CLI — human interface for project management."""

from __future__ import annotations

import click

from agendum.config import resolve_root
from agendum.models import TaskStatus
from agendum.store.board_store import BoardStore
from agendum.store.project_store import ProjectStore
from agendum.task_graph import suggest_next_task


@click.group()
@click.option("--home", is_flag=True, help="Use ~/.agendum instead of ./.agendum")
@click.pass_context
def cli(ctx: click.Context, home: bool) -> None:
    """agendum — Universal project management for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["root"] = resolve_root(home)


@cli.command()
@click.argument("name", default="agendum")
@click.pass_context
def init(ctx: click.Context, name: str) -> None:
    """Initialize .agendum/ directory."""
    root = ctx.obj["root"]
    store = ProjectStore(root)
    store.init_board(name)
    click.echo(f"Initialized agendum at {root}")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show board overview."""
    root = ctx.obj["root"]
    project_store = ProjectStore(root)
    board_store = BoardStore(root)

    projects = project_store.list_projects()
    if not projects:
        click.echo("No projects. Run: agendum init && agendum project create <name>")
        return

    for proj in projects:
        items = board_store.list_items(proj)
        by_status: dict[str, int] = {}
        for item in items:
            by_status[item.status.value] = by_status.get(item.status.value, 0) + 1

        click.echo(f"\n{proj} ({len(items)} items)")
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
def item() -> None:
    """Manage board items."""
    pass


@item.command("add")
@click.argument("project")
@click.argument("title")
@click.option("--priority", "-p", default="medium")
@click.option("--type", "item_type", default="dev")
@click.option("--depends", "-d", multiple=True, help="Item IDs this depends on")
@click.pass_context
def item_add(
    ctx: click.Context, project: str, title: str, priority: str, item_type: str, depends: tuple[str, ...]
) -> None:
    """Add a new item to the board."""
    root = ctx.obj["root"]
    from agendum.models import TaskPriority, TaskType

    store = BoardStore(root)
    created = store.create_item(
        project=project,
        title=title,
        priority=TaskPriority(priority),
        type=TaskType(item_type),
        depends_on=list(depends),
    )
    click.echo(f"Created {created.id}: {created.title}")


@item.command("list")
@click.argument("project")
@click.option("--status", "-s", default=None)
@click.pass_context
def item_list(ctx: click.Context, project: str, status: str | None) -> None:
    """List items in a project."""
    root = ctx.obj["root"]
    store = BoardStore(root)
    status_enum = None
    if status:
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            valid = ", ".join(s.value for s in TaskStatus)
            click.echo(f"Invalid status '{status}'. Valid: {valid}", err=True)
            return
    items = store.list_items(project, status=status_enum)

    for item in items:
        click.echo(f"  [{item.status.value:^11}] {item.id}: {item.title} ({item.priority.value})")


@cli.command()
@click.argument("project")
@click.pass_context
def next(ctx: click.Context, project: str) -> None:
    """Suggest the next item to work on."""
    root = ctx.obj["root"]
    store = BoardStore(root)
    items = store.list_items(project)
    suggested = suggest_next_task(items)

    if not suggested:
        click.echo("No items available.")
        return

    click.echo(f"Next: {suggested.id}: {suggested.title} ({suggested.priority.value})")
    if suggested.notes:
        click.echo(f"  Notes: {suggested.notes[:200]}")


@cli.command()
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start the MCP server (stdio transport)."""
    import os

    # Set root for server
    os.environ["AGENDUM_ROOT"] = str(ctx.obj["root"])

    from agendum.server import mcp

    mcp.run(transport="stdio")


if __name__ == "__main__":
    cli()
