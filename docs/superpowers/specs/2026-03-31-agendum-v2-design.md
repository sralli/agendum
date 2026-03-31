# Agendum v2: Project Memory + Scoping Engine

## Context

Agendum is a 32-tool MCP server for AI agent project management. Despite being architecturally sophisticated (orchestrator pipeline, context enrichment, model routing, multi-agent coordination), it's never actually used in practice. The harness (Claude Code + superpowers + plan mode) already handles single-session orchestration, so agendum's orchestrator gets bypassed entirely.

**The problem:** Every session starts from zero. Plans, decisions, progress, and patterns evaporate. Work sprawls beyond intended scope. There's no consistent workflow because the harness and agendum compete rather than complement each other.

**The goal:** Rethink agendum as two things the harness does NOT provide:
1. **Project Memory** — Persistent state (task progress, decisions, patterns) that survives sessions
2. **Scoping Engine** — Bounded work packages with clear entry/exit criteria, derived from harness plans

Agendum stops competing with the harness and starts augmenting it.

## Design

### Separation of Concerns

| Concern | Owner | Why |
|---------|-------|-----|
| Brainstorming & design | Superpowers (brainstorming skill) | Already works well |
| Planning & task breakdown | Superpowers (writing-plans) + plan mode | Already works well |
| Subagent dispatch | Claude Code Agent tool | Native, context-aware |
| Session-level task tracking | Claude Code TaskCreate/TaskUpdate | Built-in, ephemeral |
| **Persistent project state** | **Agendum** | Nothing else does this |
| **Bounded work packages** | **Agendum** | Nothing else does this |
| **Cross-session memory** | **Agendum** | Nothing else does this |
| **Project board / backlog** | **Agendum** | Nothing else does this |

### Core Concepts

**Board** — Per-project persistent backlog. Tasks, ideas, bugs, features live here indefinitely. Not everything needs to be planned or executed. The board is the parking lot.

**Plan** — A scoped subset of board items (or new items) with dependencies, acceptance criteria, and boundaries. Created by ingesting a harness plan file. One active plan per project at a time.

**Work Package** — What `pm_next` returns. A bounded, context-rich unit of work: what to do, which files to touch, what NOT to touch, acceptance criteria, relevant decisions/patterns from memory. The agent executes within these boundaries.

**Memory** — Three scopes, kept from v1:
- `decisions` — Why we chose X over Y, with rationale
- `patterns` — Discovered conventions, gotchas, what worked
- `learnings` — Cross-project knowledge (carries to future projects)

**Status Brief** — What `pm_status` returns on session resume. A concise standup: what's done, what's in progress, what's next, key recent decisions, any blockers.

### Tool Surface (~11 tools, down from 32)

| Tool | Signature | Purpose |
|------|-----------|---------|
| `pm_init` | `()` | Initialize agendum board at `.agendum/` |
| `pm_project` | `(action: create\|list\|get, name?, description?)` | Project CRUD (single tool, action-based) |
| `pm_status` | `(project)` | Status brief for session resume |
| `pm_add` | `(project, title, type?, priority?, notes?)` | Add item to board (low ceremony) |
| `pm_board` | `(project, filter_status?, filter_type?)` | View/filter the project board |
| `pm_ingest` | `(project, plan_file)` | Read plan file → create bounded tasks with deps, criteria, key_files |
| `pm_next` | `(project)` | Get next scoped work package from active plan |
| `pm_done` | `(project, task_id, decisions?, patterns?, files_changed?)` | Report completion + auto-update memory |
| `pm_block` | `(project, task_id, reason)` | Report a blocker |
| `pm_memory` | `(project, action: read\|write\|search, scope?, content?, query?)` | Read/write/search project memory |
| `pm_learn` | `(entry, tags?)` | Record cross-project learning (global, not project-scoped) |

### What Gets Cut

| v1 Feature | Disposition | Why |
|------------|-------------|-----|
| `pm_orchestrate_plan` | **Cut** — replaced by `pm_ingest` | Harness plans, agendum ingests |
| `pm_orchestrate_approve` | **Cut** | Plan mode already has approval |
| `pm_orchestrate_next` | **Renamed** → `pm_next` | Simplified, still returns work packages |
| `pm_orchestrate_report` | **Renamed** → `pm_done` | Simplified, auto-updates memory |
| `pm_orchestrate_review` | **Cut** | Harness handles code review (superpowers:requesting-code-review) |
| `pm_orchestrate_policy` | **Cut** | Model routing is harness concern |
| `pm_orchestrate_status` | **Merged** into `pm_status` | One status tool, not two |
| `pm_agent_*` (4 tools) | **Cut** | Multi-agent out of scope for v2 |
| `pm_task_create/claim/progress/complete/handoff/next` (6 tools) | **Replaced** by `pm_add/pm_done` | Simpler lifecycle |
| `pm_task_archive/archive_all` | **Cut** | Auto-archive on completion |
| `pm_check_deps` | **Internalized** | Cycle detection happens inside `pm_ingest` |
| `pm_board_init/pm_board_status` | **Renamed** → `pm_init/pm_status` | Cleaner names |
| Context enrichment pipeline | **Kept** inside `pm_next` | Still enriches work packages with memory, patterns, decisions |
| Execution traces | **Kept** but simplified | Append-only completion records |

### The Flow in Practice

#### Starting a new project
```
User: "I want to build an auth system"

1. Harness: superpowers:brainstorming → design
2. Harness: superpowers:writing-plans → plan file at docs/superpowers/specs/...
3. Agent: pm_project("create", "auth-system", "User authentication with Clerk")
4. Agent: pm_ingest("auth-system", "docs/superpowers/specs/2026-03-31-auth-design.md")
   → Parses plan → creates 5 bounded tasks with deps, criteria, key_files
   → Auto-enriches from memory (if any cross-project learnings about auth exist)
5. Agent: pm_next("auth-system")
   → Returns work package for task-001 with boundaries and context
6. Agent dispatches subagent with work package
7. Subagent: does the work
8. Agent: pm_done("auth-system", "task-001", decisions=["Chose Clerk over Auth0"], patterns=["proxy.ts must be at project root"])
   → Auto-records to memory
9. Repeat pm_next → dispatch → pm_done
```

#### Resuming next session
```
User: "Resume auth work"

1. Agent: pm_status("auth-system")
   → "3/5 tasks done. Last worked: middleware setup.
      Key decisions: Using Clerk (not Auth0). proxy.ts at project root.
      Next: task-004 'Protected route patterns'. Blocked: nothing."
2. Agent: pm_next("auth-system")
   → Scoped work package with full context from previous sessions
3. Continue working
```

#### Adding to board without planning
```
User: "Oh, we should also add rate limiting at some point"

Agent: pm_add("auth-system", "Add rate limiting to auth endpoints", type="dev", priority="low")
→ Sits on board. Not part of any plan. Picked up whenever.
```

#### Cross-project learning
```
User: (working on a different project)

Agent: pm_learn("Clerk integration gotcha: proxy.ts must be at same level as app/ directory, not project root if using src/", tags=["auth", "clerk", "nextjs"])

Later, on a new project:
Agent: pm_ingest("new-project", plan_file)
→ pm_next enriches work packages with relevant learnings tagged "auth" or "clerk"
```

### Work Package Format (what `pm_next` returns)

```markdown
## Task: Implement Clerk middleware protection

**Scope:**
- Files to create/modify: src/proxy.ts, src/app/layout.tsx
- Files NOT to modify: src/app/api/* (API routes handled in task-005)
- Boundaries: Only auth middleware. Do not touch routing or API logic.

**Acceptance Criteria:**
- [ ] proxy.ts protects /dashboard/* routes
- [ ] Public routes (/, /sign-in, /sign-up) remain accessible
- [ ] Clerk middleware() called correctly
- [ ] Tests pass

**Context from Memory:**
- Decision: Using Clerk (chosen over Auth0 for Vercel Marketplace integration)
- Pattern: proxy.ts must be at same level as app/ directory
- Learning (cross-project): ClerkMiddleware needs NEXT_PUBLIC_CLERK_SIGN_IN_URL set

**Dependencies Completed:**
- task-001: Clerk SDK installed and configured
- task-002: Sign-in/sign-up pages created

**Constraints:**
- Do not modify existing API route handlers
- Must work with Next.js 16 proxy.ts pattern (not middleware.ts)
```

### Storage Format Changes

**Minimal changes to on-disk format.** Keep Markdown + YAML frontmatter in `.agendum/`. Main changes:

- Board items stored in `projects/<project>/board/` (replaces `tasks/`)
- Plans stored in `projects/<project>/plans/` (same as v1)
- Global learnings in `.agendum/learnings/` (new, tag-based)
- Memory files unchanged: `.agendum/memory/`
- Traces simplified but same location

### Implementation Strategy

This is a **major refactor** of agendum. The approach:

1. **Design the new models** — Slim down models.py (cut Agent, orchestrator models, add WorkPackage)
2. **Rebuild the store layer** — BoardStore (replaces TaskStore), simplified PlanStore, LearningsStore (new)
3. **Rebuild the tools layer** — 11 tools in a flat structure (no orchestrator/ subdirectory)
4. **Port context enrichment** — Keep the enrichment pipeline but integrate it into pm_next
5. **Port plan ingestion** — New pm_ingest that reads harness plan files (markdown) and creates bounded tasks
6. **Update CLAUDE.md** — New workflow documentation
7. **Update README** — New positioning, examples, quick start
8. **Tests** — Full test coverage for the new tool surface

### Key Files to Modify

- `src/agendum/models.py` — Slim down, add WorkPackage, BoardItem
- `src/agendum/server.py` — Register new tools, remove old ones
- `src/agendum/store/task_store.py` → `board_store.py`
- `src/agendum/store/plan_store.py` — Simplify
- `src/agendum/store/learnings_store.py` — New
- `src/agendum/tools/` — Rewrite to 11 tools
- `src/agendum/tools/orchestrator/` — Delete (enrichment.py and sources.py move to core)
- `CLAUDE.md` — New workflow
- `README.md` — New positioning
- `tests/` — Rewrite

### Verification

1. All existing tests that cover kept functionality should still pass (adapted)
2. New tests for all 11 tools
3. Manual test: create a project, ingest a plan, run pm_next, pm_done, pm_status cycle
4. Manual test: pm_add items to board without a plan
5. Manual test: pm_learn + verify cross-project enrichment in pm_next
6. `uv run pytest` passes
7. `uv run ruff check src/ tests/` passes
