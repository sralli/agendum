"""MCP tool registrations — 11 tools from pm_init through pm_learn."""

from __future__ import annotations

import re
from pathlib import Path

from agendum.models import BoardItem, TaskPriority, TaskStatus, TaskType, WorkPackage
from agendum.task_graph import (
    detect_cycles,
    resolve_completions,
    suggest_next_task,
    topological_levels,
)


def _parse_csv(value: str) -> list[str]:
    """Parse comma-separated string into list, stripping whitespace."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def register(mcp, stores, enricher) -> None:  # noqa: C901
    """Register all 11 v2 MCP tools on the given FastMCP instance."""

    # ── 1. pm_init ──────────────────────────────────────────────────────
    @mcp.tool(
        description="Initialize the agendum board directory. Call once per repository or home directory to set up project tracking. Creates .agendum/ with projects, learnings, and memory subdirectories. Returns confirmation. Next step: create a project with pm_project."
    )
    def pm_init(name: str = "agendum") -> str:
        try:
            stores.project.init_board(name)
            return (
                f"Board '{name}' initialized." + '\n\n> Next: pm_project("create", "my-project", "Project description")'
            )
        except Exception as e:
            return f"Error: {e}"

    # ── 2. pm_project ───────────────────────────────────────────────────
    @mcp.tool(
        description="Create, list, or get projects. Actions: 'create' (requires name), 'list' (shows all projects), 'get' (shows project details with spec/plan excerpts). Call after pm_init to set up a project, or anytime to inspect existing projects."
    )
    def pm_project(action: str, name: str = "", description: str = "") -> str:
        try:
            if action == "create":
                if not name:
                    return "Error: name is required for create"
                proj = stores.project.create_project(name, description)
                return (
                    f"Project '{proj.name}' created."
                    + f'\n\n> Next: pm_ingest("{name}", "path/to/plan.md") or pm_add("{name}", "task title")'
                )
            elif action == "list":
                projects = stores.project.list_projects()
                if not projects:
                    return "No projects found."
                return (
                    "**Projects:**\n"
                    + "\n".join(f"- {p}" for p in projects)
                    + '\n\n> Next: pm_status("project-name") or pm_project("get", "project-name")'
                )
            elif action == "get":
                if not name:
                    return "Error: name is required for get"
                proj = stores.project.get_project(name)
                if not proj:
                    return f"Error: project '{name}' not found"
                lines = [f"# {proj.name}"]
                if proj.description:
                    lines.append(f"\n{proj.description}")
                if proj.spec:
                    excerpt = proj.spec[:500]
                    lines.append(f"\n**Spec excerpt:**\n{excerpt}")
                if proj.plan:
                    excerpt = proj.plan[:500]
                    lines.append(f"\n**Plan excerpt:**\n{excerpt}")
                return "\n".join(lines) + f'\n\n> Next: pm_next("{name}") or pm_board("{name}")'
            else:
                return f"Error: unknown action '{action}'. Use create, list, or get."
        except Exception as e:
            return f"Error: {e}"

    # ── 3. pm_status ────────────────────────────────────────────────────
    @mcp.tool(
        description="Get a status overview for one or all projects. Shows item counts by status, recent progress, recent decisions, and suggested next task. Call at the start of a session to understand current state, or after completing work to see what's next."
    )
    def pm_status(project: str = "") -> str:
        try:
            if not project:
                # All-project overview
                projects = stores.project.list_projects()
                if not projects:
                    return "No projects found. Run `pm_init` and `pm_project create`."
                lines = ["# Board Status\n"]
                for p in projects:
                    items = stores.board.list_items(p)
                    counts = _count_by_status(items)
                    total = len(items)
                    lines.append(f"## {p} ({total} items)")
                    lines.append(_format_counts(counts))
                    lines.append("")
                return (
                    "\n".join(lines)
                    + '\n\n> Next: pm_status("project-name") for details, or pm_next("project-name") to start working'
                )

            # Single-project status
            items = stores.board.list_items(project)
            if not items:
                return f"No items found for project '{project}'."

            counts = _count_by_status(items)

            lines = [f"# {project} Status\n"]
            lines.append(_format_counts(counts))

            # Last 3 progress entries across all items
            all_progress = []
            for item in items:
                for entry in item.progress:
                    all_progress.append((entry.timestamp, item.id, entry.message))
            all_progress.sort(key=lambda x: x[0], reverse=True)
            if all_progress:
                lines.append("\n**Recent Progress:**")
                for _ts, item_id, msg in all_progress[:3]:
                    lines.append(f"- [{item_id}] {msg}")

            # Last 3 memory entries from "decisions" scope
            decisions = stores.memory.read("decisions")
            if decisions:
                dec_lines = [line.strip() for line in decisions.splitlines() if line.strip()]
                lines.append("\n**Recent Decisions:**")
                for d in dec_lines[-3:]:
                    lines.append(d if d.startswith("-") else f"- {d}")

            # Suggested next item
            suggested = suggest_next_task(items)
            if suggested:
                lines.append(f"\n**Suggested Next:** {suggested.id} — {suggested.title}")

            return "\n".join(lines) + f'\n\n> Next: pm_next("{project}") to get a scoped work package'
        except Exception as e:
            return f"Error: {e}"

    # ── 4. pm_add ───────────────────────────────────────────────────────
    @mcp.tool(
        description="Add a new item to a project board. Supports type (dev/docs/ops/research/review/planning/personal/email), priority (critical/high/medium/low), tags, dependencies, acceptance criteria, key files, constraints, and notes. Use for ad-hoc tasks not from a plan file."
    )
    def pm_add(
        project: str,
        title: str,
        type: str = "dev",
        priority: str = "medium",
        tags: str = "",
        depends_on: str = "",
        acceptance_criteria: str = "",
        key_files: str = "",
        constraints: str = "",
        notes: str = "",
    ) -> str:
        try:
            item = stores.board.create_item(
                project,
                title,
                type=TaskType(type),
                priority=TaskPriority(priority),
                tags=_parse_csv(tags),
                depends_on=_parse_csv(depends_on),
                acceptance_criteria=_parse_csv(acceptance_criteria),
                key_files=_parse_csv(key_files),
                constraints=_parse_csv(constraints),
                notes=notes,
            )
            return (
                f"Created {item.id}: {item.title}"
                + f'\n\n> Next: pm_next("{project}") to get a work package, or pm_add("{project}", "another task") to add more'
            )
        except Exception as e:
            return f"Error: {e}"

    # ── 5. pm_board ─────────────────────────────────────────────────────
    @mcp.tool(
        description="View the project board with optional filters. Filter by status (pending/in_progress/blocked/done), tag, or type. Returns a markdown table of all matching items. Use to survey the full backlog or check status of specific categories."
    )
    def pm_board(project: str, status: str = "", tag: str = "", type: str = "") -> str:
        try:
            status_filter = TaskStatus(status) if status else None
            items = stores.board.list_items(project, status=status_filter, tag=tag or None)
            if type:
                items = [i for i in items if i.type == TaskType(type)]
            if not items:
                return "No items found."
            lines = ["| ID | Title | Status | Priority | Tags |", "| --- | --- | --- | --- | --- |"]
            for item in items:
                tag_str = ", ".join(item.tags) if item.tags else ""
                lines.append(f"| {item.id} | {item.title} | {item.status} | {item.priority} | {tag_str} |")
            return "\n".join(lines) + f'\n\n> Next: pm_next("{project}") to get the next work package'
        except Exception as e:
            return f"Error: {e}"

    # ── 6. pm_ingest ────────────────────────────────────────────────────
    @mcp.tool(
        description="Import tasks from a markdown plan file into the project board. Parses headings as task titles, extracts acceptance criteria, key files, and dependencies. Creates bounded board items with dependency tracking. Call after creating a project to populate the board from an existing plan."
    )
    def pm_ingest(project: str, plan_file: str) -> str:
        try:
            content = Path(plan_file).read_text(encoding="utf-8")
            tasks = _parse_plan_markdown(content)

            created_items: list[BoardItem] = []
            for task_data in tasks:
                item = stores.board.create_item(project, task_data["title"], **task_data["kwargs"])
                created_items.append(item)

            # Check for cycles
            all_items = stores.board.list_items(project)
            cycles = detect_cycles(all_items)
            levels = topological_levels(all_items)

            lines = [f"Ingested {len(created_items)} items from {plan_file}."]
            lines.append(f"Dependency levels: {len(levels)}")
            if cycles:
                lines.append(f"WARNING: {len(cycles)} dependency cycle(s) detected!")
                for cycle in cycles:
                    lines.append(f"  Cycle: {' -> '.join(cycle)}")
            return "\n".join(lines) + f'\n\n> Next: pm_next("{project}") to get your first work package'
        except Exception as e:
            return f"Error: {e}"

    # ── 7. pm_next ──────────────────────────────────────────────────────
    @mcp.tool(
        description="Get the next scoped work package. Returns a bounded context packet with task details, acceptance criteria, relevant memory, dependency context, and project rules. Automatically marks the task as in-progress. Call at the start of a work session or after completing a task with pm_done."
    )
    def pm_next(project: str) -> str:
        try:
            items = stores.board.list_items(project)
            suggested = suggest_next_task(items)
            if not suggested:
                return "No tasks available. All tasks are done, blocked, or in progress."

            complexity, estimated_scope = _compute_complexity(suggested)

            package = WorkPackage(
                item=suggested,
                scope=", ".join(suggested.key_files) if suggested.key_files else "",
                exit_criteria=list(suggested.acceptance_criteria),
                constraints=list(suggested.constraints),
                key_files=list(suggested.key_files),
                complexity=complexity,
                estimated_scope=estimated_scope,
            )

            # Budget scales with task complexity
            complexity_budgets = {
                "trivial": (4000, {"project_rules": 1500, "dependency_context": 1000, "memory_context": 1000}),
                "small": (6000, {"project_rules": 2000, "dependency_context": 1500, "memory_context": 1500}),
                "medium": (8000, {"project_rules": 2500, "dependency_context": 2000, "memory_context": 2000}),
                "large": (10000, {"project_rules": 3000, "dependency_context": 2500, "memory_context": 2500}),
            }
            max_chars, field_budgets = complexity_budgets.get(complexity, complexity_budgets["medium"])
            package = enricher.enrich(
                package, suggested, project, max_context_chars=max_chars, field_budgets=field_budgets
            )

            # Mark as in_progress
            stores.board.update_item(project, suggested.id, status=TaskStatus.IN_PROGRESS)

            # Format output
            lines = [f"## Task: {suggested.title}\n"]
            lines.append(f"**Complexity:** {complexity} ({estimated_scope})")
            lines.append("")
            if package.key_files:
                lines.append("**Scope:**")
                lines.append(f"- Files to create/modify: {', '.join(package.key_files)}")
                lines.append("")
            if package.exit_criteria:
                lines.append("**Acceptance Criteria:**")
                for criterion in package.exit_criteria:
                    lines.append(f"- [ ] {criterion}")
                lines.append("")
            if package.memory_context:
                lines.append("**Context from Memory:**")
                lines.append(package.memory_context)
                lines.append("")
            if package.dependency_context:
                lines.append("**Dependencies Completed:**")
                lines.append(package.dependency_context)
                lines.append("")
            if package.constraints:
                lines.append("**Constraints:**")
                for constraint in package.constraints:
                    lines.append(f"- {constraint}")
                lines.append("")
            return (
                "\n".join(lines)
                + f'\n\n> Next: Implement the task, verify it works (run tests), then call pm_done("{project}", "{suggested.id}", verified=True) when finished'
            )
        except Exception as e:
            return f"Error: {e}"

    # ── 8. pm_done ──────────────────────────────────────────────────────
    @mcp.tool(
        description="Report task completion. Records decisions, patterns, and learnings to project memory, logs files changed, and auto-unblocks dependent tasks. Pass decisions for architectural choices worth remembering, patterns for reusable conventions, and learnings for project-scoped insights. Set verified=True after running tests to mark as verified."
    )
    def pm_done(
        project: str,
        item_id: str,
        decisions: str = "",
        patterns: str = "",
        files_changed: str = "",
        notes: str = "",
        learnings: str = "",
        verified: bool = False,
        verification_notes: str = "",
        auto_extract: bool = True,
    ) -> str:
        try:
            # Auto-extract from git if no files_changed provided
            if auto_extract and not files_changed:
                from agendum.env_context import get_git_diff_stat, get_last_commit_message

                diff_stat = get_git_diff_stat()
                commit_msg = get_last_commit_message()
                if diff_stat:
                    files_changed = f"(auto-extracted from latest commit)\n{diff_stat}"
                if commit_msg and not notes:
                    notes = f"Latest commit: {commit_msg}"

            # Set status to done and verified flag
            stores.board.update_item(project, item_id, status=TaskStatus.DONE, verified=verified)

            # Add progress entry
            progress_parts = []
            if verified:
                progress_parts.append("Verified")
                if verification_notes:
                    progress_parts.append(verification_notes)
            else:
                progress_parts.append("Unverified completion")
            if files_changed:
                progress_parts.append(f"Files: {files_changed}")
            if notes:
                progress_parts.append(f"Notes: {notes}")
            progress_msg = ". ".join(progress_parts) + "."
            stores.board.add_progress(project, item_id, "agent", progress_msg)

            # Handle decisions
            decision_list = _parse_csv(decisions)
            if decision_list:
                # Update item decisions
                item = stores.board.get_item(project, item_id)
                if item:
                    existing = list(item.decisions)
                    existing.extend(decision_list)
                    stores.board.update_item(project, item_id, decisions=existing)
                # Append to memory
                for d in decision_list:
                    stores.memory.append("decisions", d, author="agent")

            # Handle patterns
            pattern_list = _parse_csv(patterns)
            for p in pattern_list:
                stores.memory.append("patterns", p, author="agent")

            # Handle learnings (project-scoped)
            learning_list = _parse_csv(learnings)
            if learning_list:
                item = stores.board.get_item(project, item_id)
                item_tags = list(item.tags) if item else []
                for entry in learning_list:
                    stores.learnings.add_learning(entry, item_tags, project=project)

            # Resolve completions — unblock dependents
            all_items = stores.board.list_items(project)
            unblocked = resolve_completions(all_items, item_id)
            for uid in unblocked:
                stores.board.update_item(project, uid, status=TaskStatus.PENDING)

            result = f"Marked {item_id} as done."
            if unblocked:
                result += f" Unblocked: {', '.join(unblocked)}"
                result += f'\n\n> Next: pm_next("{project}") to continue with newly unblocked tasks'
            else:
                result += f'\n\n> Next: pm_next("{project}") for the next task, or pm_status("{project}") for overview'
            return result
        except Exception as e:
            return f"Error: {e}"

    # ── 9. pm_block ─────────────────────────────────────────────────────
    @mcp.tool(
        description="Report a task as blocked with a reason. Updates the task status and logs the blocker. Use when a task cannot proceed due to external dependencies, missing information, or upstream blockers."
    )
    def pm_block(project: str, item_id: str, reason: str) -> str:
        try:
            stores.board.update_item(project, item_id, status=TaskStatus.BLOCKED)
            stores.board.add_progress(project, item_id, "agent", f"Blocked: {reason}")
            return (
                f"Blocked {item_id}: {reason}"
                + f'\n\n> Next: Resolve the blocker, then pm_done("{project}", "{item_id}") or pm_next("{project}") for other tasks'
            )
        except Exception as e:
            return f"Error: {e}"

    # ── 10. pm_memory ───────────────────────────────────────────────────
    @mcp.tool(
        description="Read, write, append, or search project memory. Scopes: 'decisions' (architectural choices), 'patterns' (conventions and gotchas), 'project' (general project knowledge), 'learnings' (cross-project insights). Use to persist or retrieve knowledge across sessions."
    )
    def pm_memory(action: str, scope: str = "", content: str = "", query: str = "", author: str = "") -> str:
        try:
            if action == "read":
                if not scope:
                    return "Error: scope is required for read"
                result = stores.memory.read(scope)
                result = result if result else f"No content in scope '{scope}'."
                return (
                    result
                    + '\n\n> Next: pm_next("project") to continue working, or pm_memory("append", "scope", "new insight") to add more'
                )
            elif action == "write":
                if not scope or not content:
                    return "Error: scope and content are required for write"
                stores.memory.write(scope, content)
                return (
                    f"Wrote to memory scope '{scope}'."
                    + '\n\n> Next: Continue working or pm_next("project") for the next task'
                )
            elif action == "append":
                if not scope or not content:
                    return "Error: scope and content are required for append"
                stores.memory.append(scope, content, author=author or None)
                return (
                    f"Appended to memory scope '{scope}'."
                    + '\n\n> Next: Continue working or pm_next("project") for the next task'
                )
            elif action == "search":
                if not query:
                    return "Error: query is required for search"
                results = stores.memory.search(query)
                if not results:
                    return (
                        "No matches found."
                        + '\n\n> Next: pm_next("project") to continue working, or pm_memory("append", "scope", "new insight") to add more'
                    )
                lines = ["**Memory Search Results:**"]
                for s, matches in results.items():
                    lines.append(f"\n__{s}__:")
                    for m in matches:
                        lines.append(f"- {m}")
                return (
                    "\n".join(lines)
                    + '\n\n> Next: pm_next("project") to continue working, or pm_memory("append", "scope", "new insight") to add more'
                )
            else:
                return f"Error: unknown action '{action}'. Use read, write, append, or search."
        except Exception as e:
            return f"Error: {e}"

    # ── 11. pm_learn ────────────────────────────────────────────────────
    @mcp.tool(
        description="Record a learning. Pass 'project' for project-scoped learning, omit for global cross-project learning. Tagged insights enrich future work packages. Use for patterns, gotchas, or conventions. Examples: 'Clerk proxy.ts must be at app/ level' tagged 'auth,clerk,nextjs'."
    )
    def pm_learn(content: str, tags: str = "", source_project: str = "", project: str = "") -> str:
        try:
            tag_list = _parse_csv(tags)
            learning_id = stores.learnings.add_learning(
                content, tag_list, source_project or None, project=project or None
            )
            scope_label = f"project '{project}'" if project else "global"
            return (
                f"Learning {learning_id} added ({scope_label})."
                + '\n\n> Next: Continue working or pm_next("project") for the next task'
            )
        except Exception as e:
            return f"Error: {e}"


# ── Helpers ─────────────────────────────────────────────────────────────


def _compute_complexity(item: BoardItem) -> tuple[str, str]:
    """Compute complexity level and estimated scope from item metadata.

    Returns (complexity_level, estimated_scope_description).
    """
    # Base level from key_files count
    file_count = len(item.key_files)
    if file_count <= 1:
        level = 0  # trivial
    elif file_count <= 3:
        level = 1  # small
    elif file_count <= 6:
        level = 2  # medium
    else:
        level = 3  # large

    # Adjust for acceptance criteria count
    ac_count = len(item.acceptance_criteria)
    if ac_count <= 1:
        level -= 1
    elif ac_count >= 4:
        level += 1

    # Adjust for dependency count
    dep_count = len(item.depends_on)
    if dep_count == 0:
        level -= 1
    elif dep_count >= 3:
        level += 1

    # Clamp to valid range
    level = max(0, min(3, level))

    levels = ["trivial", "small", "medium", "large"]
    complexity = levels[level]

    # Build estimated scope description
    parts = []
    if file_count == 0:
        parts.append("No files specified")
    elif file_count == 1:
        parts.append(f"Single-file change ({item.key_files[0]})")
    else:
        parts.append(f"{file_count}-file change")

    if ac_count > 0:
        parts.append(f"{ac_count} criteria")
    if dep_count > 0:
        parts.append(f"{dep_count} dependencies")

    estimated_scope = ", ".join(parts)

    return complexity, estimated_scope


def _count_by_status(items: list[BoardItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.status)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _format_counts(counts: dict[str, int]) -> str:
    parts = []
    for status in ("pending", "in_progress", "blocked", "done"):
        count = counts.get(status, 0)
        if count:
            parts.append(f"{status}: {count}")
    return " | ".join(parts) if parts else "No items"


def _parse_plan_markdown(content: str) -> list[dict]:
    """Parse a markdown plan file into task data dicts.

    Headings (## or ###) become task titles. Under each heading:
    - Regular text/bullets -> notes
    - **Acceptance Criteria:** section -> acceptance_criteria list
    - **Files:** line -> key_files
    - **Depends:** line -> depends_on (maps "Task N" to "item-00N")
    """
    tasks: list[dict] = []
    heading_pattern = re.compile(r"^#{2,3}\s+(?:Task\s+\d+:\s*)?(.+)$")

    current_task: dict | None = None
    in_ac = False  # inside acceptance criteria section

    for line in content.splitlines():
        heading_match = heading_pattern.match(line)

        if heading_match:
            # Save previous task
            if current_task:
                tasks.append(current_task)

            title = heading_match.group(1).strip()
            current_task = {"title": title, "kwargs": {}, "_notes_lines": []}
            in_ac = False
            continue

        if current_task is None:
            continue

        stripped = line.strip()

        # Check for **Acceptance Criteria:**
        if stripped.startswith("**Acceptance Criteria:**"):
            in_ac = True
            continue

        # Check for **Files:** line
        if stripped.startswith("**Files:**"):
            files_str = stripped.replace("**Files:**", "").strip()
            current_task["kwargs"]["key_files"] = _parse_csv(files_str)
            in_ac = False
            continue

        # Check for **Depends:** line
        if stripped.startswith("**Depends:**"):
            deps_str = stripped.replace("**Depends:**", "").strip()
            dep_ids = []
            for dep_ref in _parse_csv(deps_str):
                match = re.match(r"Task\s+(\d+)", dep_ref)
                if match:
                    dep_ids.append(f"item-{int(match.group(1)):03d}")
                else:
                    dep_ids.append(dep_ref)
            current_task["kwargs"]["depends_on"] = dep_ids
            in_ac = False
            continue

        # If in acceptance criteria section, collect bullet items
        if in_ac and stripped.startswith("- "):
            current_task["kwargs"].setdefault("acceptance_criteria", []).append(stripped[2:])
            continue

        # If we hit another bold section, exit AC mode
        if in_ac and stripped.startswith("**"):
            in_ac = False

        # Regular notes
        if stripped:
            current_task["_notes_lines"].append(stripped)

    # Save last task
    if current_task:
        tasks.append(current_task)

    # Convert notes lines to string
    for task_data in tasks:
        notes_lines = task_data.pop("_notes_lines", [])
        if notes_lines:
            task_data["kwargs"]["notes"] = "\n".join(notes_lines)

    return tasks
