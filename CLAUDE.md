# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

REST API for notes (CRUD, FastAPI, SQLite via SQLAlchemy 2.0, Pydantic v2) plus a PySide6 desktop GUI that consumes it. The project is built incrementally; only the skeleton (`GET /health`) exists so far. Add dependencies to `pyproject.toml` only when the step that needs them arrives.

## Commands

The venv has no system `python3-venv` package: it was created with `python3 -m venv --without-pip .venv`, then pip was bootstrapped with `python3 -m pip --python .venv/bin/python install pip`. Always use the `.venv/bin/` binaries.

```bash
.venv/bin/pip install -e ".[dev]"                     # install (dev extras: pytest, httpx)
.venv/bin/pytest -v                                   # all tests
.venv/bin/pytest tests/backend/test_health.py::test_health_returns_ok   # single test
.venv/bin/uvicorn backend.main:app --reload           # run API, docs at /docs
```

Planned and not set up yet: `ruff` (lint/format), `pytest-cov` (threshold 90%), and `pre-commit` hooks. Once they exist, Qt tests must run with `QT_QPA_PLATFORM=offscreen`.

## Workflow rules

- **Strict TDD**: write the failing test first, run it to see it fail, write the minimal code, then refactor. Commit only when tests are green, because the planned pre-commit hook blocks commits on syntax errors, test collection errors, lint failures or failing tests. Never use `--no-verify`.
- Planned Git flow: one branch per step, PR to `main`, merge only when CI is green (GitHub Actions: `lint`, `test-backend`, `test-desktop`). The local branch is currently `master` and has no remote yet.

## Architecture (target)

- `backend/` is layered as `routers/` (HTTP only) → `crud.py` (data access, no HTTP) → `models.py` (ORM). `schemas.py` holds the Pydantic I/O models, kept separate from the ORM models. `database.get_db()` is a FastAPI dependency, so tests override it with an in-memory SQLite engine (`StaticPool`).
- `desktop/` uses three layers so the GUI stays testable:
  - `NotesClient` wraps an injected `httpx.Client`. Tests pass the FastAPI `TestClient`, so the client talks to the real API without network. It maps 404, 422 and connection errors to domain exceptions.
  - The `Presenter` holds all UI logic, has no Qt dependency, and is tested with fake client and view objects.
  - The PySide6 view stays thin and is tested with `pytest-qt` (`qtbot`).
- `tests/` mirrors the packages: `tests/backend/` and `tests/desktop/`.

## Rules
- Always run `pytest -q` before telling a task is done
- Type hints mandatory, no dependance without asking me
- small commits, messages following the conventionnal commits convention https://www.conventionalcommits.org/en/v1.0.0/
