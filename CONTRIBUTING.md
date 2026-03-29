# Contributing to agendum

Thanks for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/sralli/agendum.git
cd agendum
uv sync          # Install all dependencies
uv run pytest    # Run tests
```

## Workflow

1. Open an issue first to discuss the change
2. Fork the repo and create a branch from `master`
3. Make your changes
4. Run `uv run ruff check .` and `uv run ruff format .`
5. Run `uv run pytest tests/ -v` — all tests must pass
6. Submit a PR with a clear description

## Code Style

- We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Line length: 120 characters
- Type hints on all public functions
- Tests for new functionality

## Project Structure

- `src/agendum/tools/` — MCP tool modules (one per domain)
- `src/agendum/store/` — File I/O layer (Markdown + YAML)
- `src/agendum/models.py` — Pydantic data models
- `src/agendum/task_graph.py` — Dependency resolution
- `tests/` — pytest test suite
