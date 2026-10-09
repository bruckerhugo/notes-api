# notes-api

> **This is a test project.** It is a sandbox for building an application by *vibe coding* with [Claude Code](https://claude.com/claude-code) and for exploring Claude's features (plan mode, TDD workflow, memory, `CLAUDE.md`, hooks, CI integration…). It is not intended for production use.

The goal is a notes application made of:

- a **REST API** (FastAPI + SQLite) exposing CRUD operations on notes,
- a **desktop GUI** (PySide6) that consumes the API.

The project is built step by step with TDD. Right now the API exposes `GET /health`, `POST /notes` and `GET /notes`. The desktop GUI does not exist yet.

## Requirements

- Python 3.12+
- Git

## Setup

```bash
git clone <repo-url> notes-api
cd notes-api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

> **Debian/Ubuntu (incl. WSL):** if `python3 -m venv` fails with *"ensurepip is not available"*, you have two options:
> - install the missing package: `sudo apt install python3.12-venv`
> - or, without `sudo`, run:
>   ```bash
>   python3 -m venv --without-pip .venv
>   python3 -m pip --python .venv/bin/python install pip
>   .venv/bin/pip install -e ".[dev]"
>   ```

## Run the API

```bash
.venv/bin/uvicorn backend.main:app --reload
```

Once it is running, you can use:

- Health check: <http://localhost:8000/health>, which should return `{"status": "ok"}`
- Interactive docs (Swagger UI): <http://localhost:8000/docs>

Notes are stored in a SQLite file, `notes.db`, in the current directory. The tables are created automatically at startup. To use another database file, set `DATABASE_URL`:

```bash
DATABASE_URL=sqlite:////tmp/notes.db .venv/bin/uvicorn backend.main:app --reload
```

### API endpoints

| Method | Route    | Description       | Responses                                  |
|--------|----------|-------------------|--------------------------------------------|
| GET    | `/health`| Health check      | `200`                                      |
| POST   | `/notes` | Create a note     | `201` created note, `422` invalid payload  |
| GET    | `/notes` | List notes (ordered by id), paginated with `skip` (≥ 0, default 0) and `limit` (1–100, default 100) | `200` list of notes, `422` invalid params |

Example:

```bash
curl -X POST http://localhost:8000/notes \
     -H 'Content-Type: application/json' \
     -d '{"title": "Groceries", "content": "Milk, bread"}'
# {"id":1,"title":"Groceries","content":"Milk, bread","created_at":"...","updated_at":"..."}

curl 'http://localhost:8000/notes?skip=0&limit=10'
# [{"id":1,"title":"Groceries",...}]
```

`title` is required (1–200 characters). `content` is optional and defaults to `""`.

## Tests

The tests use **pytest**. They run against an **in-memory SQLite database**, which is created fresh for every test. Your `notes.db` is never touched, and no server needs to be running.

### Run the tests

```bash
.venv/bin/pytest                    # whole suite
.venv/bin/pytest -q                 # quiet output
.venv/bin/pytest -v                 # one line per test
.venv/bin/pytest tests/backend/test_api_notes.py                                   # one file
.venv/bin/pytest tests/backend/test_health.py::test_health_returns_ok              # one test
.venv/bin/pytest -k "create_note and not title"                                    # by name expression
.venv/bin/pytest -x                 # stop at the first failure
.venv/bin/pytest --lf               # re-run only the tests that failed last time
```

### Coverage

Coverage is measured with [pytest-cov](https://pytest-cov.readthedocs.io/). It is configured in `pyproject.toml` to measure the `backend` package, include branch coverage, and list the missing lines.

```bash
.venv/bin/pytest --cov                                  # summary in the terminal
.venv/bin/pytest --cov --cov-report=html                # HTML report, then open htmlcov/index.html
.venv/bin/pytest --cov --cov-fail-under=90              # fail if total coverage < 90%
```

Example output:

```
Name                          Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------------------
backend/crud.py                   9      0      0      0   100%
backend/database.py              12      2      0      0    83%   18-19
...
TOTAL                            72      4      0      0    94%
```

### Test layout

- `tests/conftest.py`: shared fixtures.
  - `client`: a FastAPI `TestClient` wired to the in-memory database.
  - `db_session`: a SQLAlchemy session, to check the database state directly.
  - `engine`: the in-memory engine; the schema is created and dropped for each test.
- `tests/backend/`: API tests, one file per feature.

## Project layout

```
backend/     FastAPI application
tests/       pytest test suite (mirrors the package layout)
CLAUDE.md    guidance for Claude Code when working in this repo
```

## Roadmap

1. ✅ Project skeleton + first passing test
2. Pre-commit hooks that block commits on syntax errors, lint failures or failing tests
3. GitHub repository + CI pipeline (GitHub Actions) + branch protection
4. ✅ Database layer (SQLAlchemy + SQLite)
5. 🚧 CRUD layer (create, list done)
6. 🚧 `/notes` REST endpoints (`POST /notes`, `GET /notes` done)
7. Desktop HTTP client
8. GUI presenter (UI logic, Qt-free)
9. PySide6 main window
10. End-to-end test + docs polish
11. Release pipeline (PyInstaller builds published as GitHub Releases)
