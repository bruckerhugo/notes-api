# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

REST API for notes (CRUD, FastAPI, SQLite via SQLAlchemy 2.0, Pydantic v2) plus a PySide6 desktop GUI that consumes it. The project is built incrementally. The REST API is complete: `GET /health`, `POST /notes`, `GET /notes` (with `skip`/`limit` pagination, ordered by id), `GET /notes/{id}`, `PATCH /notes/{id}` and `DELETE /notes/{id}` (204). `PATCH` is a partial update: it applies `NoteUpdate.model_dump(exclude_unset=True)`, and an explicit `null` returns 422. Unknown ids return 404 `{"detail": "Note not found"}` via the router helper `_get_note_or_404`. Note ids must be canonical integers in the int64 range (`NoteId`), otherwise 422. Next: GitHub CI (plan step 3), then the desktop client. The desktop GUI does not exist yet.

## Commands

The venv has no system `python3-venv` package: it was created with `python3 -m venv --without-pip .venv`, then pip was bootstrapped with `python3 -m pip --python .venv/bin/python install pip`. Always use the `.venv/bin/` binaries.

```bash
.venv/bin/pip install -e ".[dev]"                     # install (dev extras: pytest, httpx, pytest-cov, ruff, pre-commit)
.venv/bin/pre-commit install                          # install Git hooks (pre-commit + pre-push)
.venv/bin/pytest -q                                   # all tests
.venv/bin/pytest tests/backend/test_health.py::test_health_returns_ok   # single test
.venv/bin/pytest -k create_note                       # tests matching a name
.venv/bin/pytest --cov                                # coverage (config in pyproject: source=backend, branch, show_missing)
.venv/bin/pytest --cov --cov-report=html              # HTML report in htmlcov/
.venv/bin/ruff check --fix . && .venv/bin/ruff format .   # lint + format (config in pyproject)
.venv/bin/pre-commit run --all-files                  # run commit hooks manually
.venv/bin/uvicorn backend.main:app --reload           # run API (DB: sqlite:///notes.db), docs at /docs
DATABASE_URL=sqlite:////tmp/notes.db .venv/bin/uvicorn backend.main:app   # run API on another DB
```

Hooks are defined in `.pre-commit-config.yaml` and are all local, using the `.venv` binaries. The pre-commit hook runs compileall, ruff check, ruff format --check and `pytest -x`. The pre-push hook runs coverage and fails below 90%. Both hooks set `QT_QPA_PLATFORM=offscreen` for the future Qt tests.

## Workflow rules

- **Strict TDD**: write the failing test first, run it to see it fail, write the minimal code, then refactor. Commit only when tests are green, because the pre-commit hook blocks commits on syntax errors, test collection errors, lint failures or failing tests. Never use `--no-verify`.
- Planned Git flow: one branch per step, PR to `main`, merge only when CI is green (GitHub Actions: `lint`, `test-backend`, `test-desktop`). The local branch is currently `master` and has no remote yet.

## Architecture

`backend/` and the test setup are in place. `desktop/` is still the target design.


- `backend/` is layered as `routers/` (HTTP only) → `crud.py` (data access, no HTTP) → `models.py` (ORM). `schemas.py` holds the Pydantic I/O models, kept separate from the ORM models. `database.get_db()` is a FastAPI dependency, so tests override it with an in-memory SQLite engine (`StaticPool`). Tables are created by the app `lifespan` (`Base.metadata.create_all`). There are no migrations yet.
- `desktop/` uses three layers so the GUI stays testable:
  - `NotesClient` wraps an injected `httpx.Client`. Tests pass the FastAPI `TestClient`, so the client talks to the real API without network. It maps 404, 422 and connection errors to domain exceptions.
  - The `Presenter` holds all UI logic, has no Qt dependency, and is tested with fake client and view objects.
  - The PySide6 view stays thin and is tested with `pytest-qt` (`qtbot`).
- `tests/` mirrors the packages (`tests/backend/`, later `tests/desktop/`). `tests/conftest.py` provides three fixtures: `engine` (in-memory DB, schema created and dropped for each test), `db_session` (to assert directly on DB state) and `client`. `client` is a `TestClient` with `get_db` overridden. It is deliberately not used as a context manager, so the lifespan does not run and no `notes.db` file is created on disk.

## Rules
- Always run `pytest -q` before telling a task is done
- Type hints mandatory, no dependance without asking me
- small commits, messages following the conventionnal commits convention https://www.conventionalcommits.org/en/v1.0.0/
