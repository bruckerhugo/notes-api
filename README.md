# notes-api

> **This is a test project.** It is a sandbox for building an application by *vibe coding* with [Claude Code](https://claude.com/claude-code) and for exploring Claude's features (plan mode, TDD workflow, memory, `CLAUDE.md`, hooks, CI integration…). It is not intended for production use.

The goal is a notes application made of:

- a **REST API** (FastAPI + SQLite) exposing CRUD operations on notes,
- a **desktop GUI** (PySide6) that consumes the API.

The project is built step by step with TDD. Right now only the API skeleton (`GET /health`) exists.

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

## Run the tests

```bash
.venv/bin/pytest -v                                                     # whole suite
.venv/bin/pytest tests/backend/test_health.py::test_health_returns_ok   # a single test
```

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
4. Database layer (SQLAlchemy + SQLite)
5. CRUD layer
6. `/notes` REST endpoints
7. Desktop HTTP client
8. GUI presenter (UI logic, Qt-free)
9. PySide6 main window
10. End-to-end test + docs polish
11. Release pipeline (PyInstaller builds published as GitHub Releases)
