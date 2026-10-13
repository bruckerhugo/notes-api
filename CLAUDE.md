# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

REST API for notes (CRUD, FastAPI, SQLite via SQLAlchemy 2.0, Pydantic v2) plus a PySide6 desktop GUI that consumes it. The project is built incrementally. The REST API is complete: `GET /health`, `POST /notes`, `GET /notes` (with `skip`/`limit` pagination, ordered by id), `GET /notes/{id}`, `PATCH /notes/{id}` and `DELETE /notes/{id}` (204). `PATCH` is a partial update: it applies `NoteUpdate.model_dump(exclude_unset=True)`, and an explicit `null` returns 422. Unknown ids return 404 `{"detail": "Note not found"}` via the router helper `_get_note_or_404`. Note ids must be canonical integers in the int64 range (`NoteId`), otherwise 422. The PySide6 desktop app works (`python -m desktop`). Next: the end-to-end test (plan step 10), then the release pipeline (step 11).

## Commands

The venv has no system `python3-venv` package: it was created with `python3 -m venv --without-pip .venv`, then pip was bootstrapped with `python3 -m pip --python .venv/bin/python install pip`. Always use the `.venv/bin/` binaries.

```bash
.venv/bin/pip install -e ".[dev,desktop]"             # install (desktop: PySide6-Essentials; dev: pytest, httpx, pytest-cov, pytest-qt, ruff, pre-commit)
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
.venv/bin/python -m desktop                           # run the desktop app (API at NOTES_API_URL, default http://127.0.0.1:8000)
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/desktop   # Qt tests without a display
```

Hooks are defined in `.pre-commit-config.yaml` and are all local, using the `.venv` binaries. The pre-commit hook runs compileall, ruff check, ruff format --check and `pytest -x`. The pre-push hook runs coverage and fails below 90%. Both hooks set `QT_QPA_PLATFORM=offscreen` for the future Qt tests.

## Workflow rules

- **Strict TDD**: write the failing test first, run it to see it fail, write the minimal code, then refactor. Commit only when tests are green, because the pre-commit hook blocks commits on syntax errors, test collection errors, lint failures or failing tests. Never use `--no-verify`.
- Planned Git flow: one branch per step, PR to `main`, merge only when CI is green. The CI workflow is `.github/workflows/ci.yml`, with jobs `lint` (runs the pre-commit hooks), `test-backend` (Python 3.12/3.13, `--cov=backend` ≥ 90%) and `test-desktop` (`--cov=desktop` ≥ 90%). Each job limits `--cov` to its own package, otherwise the package that is not tested pulls the total under the threshold. `test-backend` installs only `.[dev]` (no Qt) and runs pytest with `-p no:pytest-qt`, because the pytest-qt plugin imports QtGui at startup and fails without the Qt system libraries. To check CI results, read the check runs from the API (`gh api repos/bruckerhugo/notes-api/commits/<sha>/check-runs`): `gh pr checks` output can be stale. `main` is protected by a ruleset: PR required, the CI checks must pass, no force push or deletion. CI recreates `.venv`, so the hooks' `.venv/bin/...` entries work unchanged. The main branch is `main`, and the remote `origin` is the public repository `github.com/bruckerhugo/notes-api`.

## Architecture

`backend/` and `desktop/` are both in place.


- `backend/` is layered as `routers/` (HTTP only) → `crud.py` (data access, no HTTP) → `models.py` (ORM). `schemas.py` holds the Pydantic I/O models, kept separate from the ORM models. `database.get_db()` is a FastAPI dependency, so tests override it with an in-memory SQLite engine (`StaticPool`). Tables are created by the app `lifespan` (`Base.metadata.create_all`). There are no migrations yet.
- `desktop/` uses three layers so the GUI stays testable:
  - `NotesClient` (done) wraps an injected `httpx.Client` and returns frozen `Note` dataclasses with UTC-aware datetimes. Tests pass the FastAPI `TestClient`, so the client talks to the real API without network. Transport failures are simulated with `httpx.MockTransport`. Errors map to `NotesApiError` subclasses: `NoteNotFound` (404, with `.note_id`), `ValidationError` (422, readable `field: msg`) and `ApiUnavailable` (connection errors and timeouts). Any other error status raises the base `NotesApiError`. `desktop/` must not import `backend/`.
  - `NotesPresenter` (done) holds all UI logic, with no Qt dependency. It depends on two `Protocol`s: `NotesApi` (implemented by `NotesClient`) and `NotesView` (`show_notes(notes, selected_id)`, `show_note(note | None)`, `show_error`, `show_status`, `confirm_delete`). It is tested with `FakeNotesClient` and `FakeView` in `tests/desktop/test_presenter.py`. Behaviour: after a create, update or delete it reloads the list and keeps the selection in sync. On `NoteNotFound` (note deleted elsewhere) it shows the error, clears the selection and reloads. On any other `NotesApiError` it only shows the error, so the editor keeps the user's input.
  - `desktop/views/main_window.py` holds `MainWindow`, a thin PySide6 view that implements `NotesView`. `bind(presenter)` connects the widgets (list click, New, Save, `Ctrl+S`, Delete) to the presenter. `show_notes` blocks signals while repopulating the list. It is tested with `pytest-qt` and a recording `FakePresenter`, and `QMessageBox.warning`/`question` are monkeypatched in tests.
  - `desktop/app.py` contains `create_window(api)`, which wires client, presenter and window, and `main()`, which reuses an existing `QApplication` so it is testable under pytest-qt. `desktop/__main__.py` is omitted from coverage.
  - Dependencies: Qt comes from `PySide6-Essentials` (extra `desktop`), not the full `PySide6`, which is too heavy. Shared test doubles live in `tests/desktop/fakes.py`.
- `tests/` mirrors the packages (`tests/backend/`, later `tests/desktop/`). `tests/conftest.py` provides three fixtures: `engine` (in-memory DB, schema created and dropped for each test), `db_session` (to assert directly on DB state) and `client`. `client` is a `TestClient` with `get_db` overridden. It is deliberately not used as a context manager, so the lifespan does not run and no `notes.db` file is created on disk.

## Rules
- Always run `pytest -q` before telling a task is done
- Type hints mandatory, no dependance without asking me
- small commits, messages following the conventionnal commits convention https://www.conventionalcommits.org/en/v1.0.0/
