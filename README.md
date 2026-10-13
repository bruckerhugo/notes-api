# notes-api

> **This is a test project.** It is a project for building an application by *vibe coding* with [Claude Code](https://claude.com/claude-code) and for exploring Claude's features (plan mode, TDD workflow, memory, `CLAUDE.md`, hooks, CI integration…). It is not intended for production use.

The goal is a notes application made of:

- a **REST API** (FastAPI + SQLite) exposing CRUD operations on notes,
- a **desktop GUI** (PySide6) that consumes the API.

The project was built step by step with TDD and is complete: a REST API (`GET /health` plus full CRUD on `/notes`), a PySide6 desktop app that lists, views, creates, edits and deletes notes, and standalone executables published on each release.

## Download the app

Each [GitHub Release](https://github.com/bruckerhugo/notes-api/releases) provides a standalone executable. It embeds the API, so there is nothing else to install or start:

| System | File | How to run |
|---|---|---|
| Linux x86_64 | `notes-linux-x86_64.tar.gz` | `tar -xzf notes-linux-x86_64.tar.gz && ./notes` |
| Windows x86_64 | `notes-windows-x86_64.exe` | Double-click it. SmartScreen may warn about an unsigned app: choose *More info → Run anyway*. |
| macOS (Apple Silicon) | `notes-macos-arm64.zip` | Unzip it, then right-click `Notes.app` and choose *Open* the first time, because the app is not signed. |

Notes are stored in `notes.db` in your user data directory:
- Linux: `~/.local/share/notes-api/`
- Windows: `%APPDATA%\notes-api\`
- macOS: `~/Library/Application Support/notes-api/`

On Linux the system needs the usual Qt runtime libraries. With X11 (not Wayland), this includes `libxcb-cursor0`, for example: `sudo apt install libxcb-cursor0 libegl1`.

## Requirements

- Python 3.12+
- Git

## Setup

```bash
git clone https://github.com/bruckerhugo/notes-api.git
cd notes-api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,desktop]"
.venv/bin/pre-commit install      # Git hooks, see "Quality gates" below
```

> **Debian/Ubuntu (incl. WSL):** if `python3 -m venv` fails with *"ensurepip is not available"*, you have two options:
> - install the missing package: `sudo apt install python3.12-venv`
> - or, without `sudo`, run:
>   ```bash
>   python3 -m venv --without-pip .venv
>   python3 -m pip --python .venv/bin/python install pip
>   .venv/bin/pip install -e ".[dev,desktop]"
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
| GET    | `/notes` | List notes (ordered by id), paginated with `skip` (0 to 2⁶³−1, default 0) and `limit` (1–100, default 100) | `200` list of notes, `422` invalid params |
| GET    | `/notes/{id}` | Get one note | `200` note, `404` note not found, `422` invalid id |
| PATCH  | `/notes/{id}` | Partially update a note: only the fields sent change | `200` updated note, `404` note not found, `422` invalid id or payload |
| DELETE | `/notes/{id}` | Delete a note | `204` no content, `404` note not found, `422` invalid id (not an integer, or outside the 64-bit range) |

Example:

```bash
curl -X POST http://localhost:8000/notes \
     -H 'Content-Type: application/json' \
     -d '{"title": "Groceries", "content": "Milk, bread"}'
# {"id":1,"title":"Groceries","content":"Milk, bread","created_at":"...","updated_at":"..."}

curl 'http://localhost:8000/notes?skip=0&limit=10'
# [{"id":1,"title":"Groceries",...}]

curl http://localhost:8000/notes/1              # 200, the note

curl -X PATCH http://localhost:8000/notes/1 \
     -H 'Content-Type: application/json' \
     -d '{"content": "Milk, bread, eggs"}'      # 200, title unchanged

curl -X DELETE http://localhost:8000/notes/1    # 204, empty body
```

`title` is required. Leading and trailing whitespace is removed, then the title must be 1–200 characters long, so a whitespace-only title is rejected. `content` is optional and defaults to `""`. For `PATCH`, both fields are optional, but sending `null` is rejected (422). `updated_at` changes on each update.

## Run the desktop app

```bash
.venv/bin/python -m desktop                 # standalone: starts its own API, notes in your user data directory
NOTES_API_URL=http://127.0.0.1:8000 .venv/bin/python -m desktop   # use an API you started yourself
.venv/bin/python -m desktop --smoke-test    # start, check the API answers, exit (used to validate builds)
```

By default the app runs the API in a background thread, on `127.0.0.1` with a free port, and stores notes in `notes.db` in your user data directory (see [Download the app](#download-the-app)). Set `NOTES_API_URL` to connect to an external API instead, for example one started with `uvicorn` as shown above.

- **Left pane:** the note list. Click a note to open it, or click **New** to start a new note.
- **Right pane:** the editor. **Save** (or `Ctrl+S`) creates or updates the note. **Delete** asks for confirmation first.
- Errors, such as an unreachable API or an invalid title, appear in a dialog. Confirmations appear in the status bar.

The `desktop` extra installs `PySide6-Essentials` (Qt widgets only, about 250 MB, instead of the 670 MB full `PySide6` package). On WSL2, the window appears through WSLg.

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
- `tests/desktop/`: desktop tests. The HTTP client is tested against the real API through `TestClient`, and network failures are simulated with `httpx.MockTransport`. The presenter is tested with an in-memory fake client and a fake view (`tests/desktop/fakes.py`). `tests/desktop/test_e2e.py` drives the real window, presenter and HTTP client against the real API (in-memory database). It covers creating, editing, deleting and cancelling a deletion, validation errors, a note deleted by another client, and an unreachable API. The Qt window is tested with [pytest-qt](https://pytest-qt.readthedocs.io/) (`qtbot`), with dialogs monkeypatched so that tests never block. Run the tests with `QT_QPA_PLATFORM=offscreen` if no display is available.

## Quality gates

Git hooks managed by [pre-commit](https://pre-commit.com/) (`.pre-commit-config.yaml`) block bad commits. Install them once after cloning with `.venv/bin/pre-commit install`.

| Hook | Runs | Blocks when |
|---|---|---|
| `pre-commit` | on every `git commit` | Python does not compile, `ruff check` or `ruff format --check` fails, or any test fails (including test collection errors) |
| `pre-push` | on every `git push` | total coverage is below 90% |

Lint and formatting use [ruff](https://docs.astral.sh/ruff/), configured in `pyproject.toml`:

```bash
.venv/bin/ruff check .               # lint
.venv/bin/ruff check --fix .         # lint and auto-fix
.venv/bin/ruff format .              # format code
.venv/bin/pre-commit run --all-files # run all commit hooks manually
```

Commit only when tests are green. Do not bypass the hooks with `--no-verify`.

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request to `main`:

| Job | What it does |
|---|---|
| `lint` | Runs the same hooks as locally (`pre-commit run --all-files`): compile check, ruff, tests |
| `test-backend` | Runs `pytest tests/backend` with coverage of `backend` on Python 3.12 and 3.13, fails below 90%, and uploads the coverage report (XML + HTML) as an artifact |
| `test-desktop` | Installs the Qt system libraries, runs `pytest tests/desktop` (offscreen Qt) with coverage of `desktop`, fails below 90%, and uploads the report |

`main` is protected: changes go through a pull request, and the CI checks must pass before merging.

## Releases

`.github/workflows/release.yml` builds the standalone executables with [PyInstaller](https://pyinstaller.org/) (`packaging/notes.spec`):

1. On a `v*` tag, it reruns the whole CI (`ci.yml` is reusable).
2. It builds the executable on Linux, Windows and macOS, and **starts each one** with `--smoke-test`: embedded API, window, API round trip.
3. It checks that the tag matches the version in `pyproject.toml`, then publishes the three files in a GitHub Release with generated release notes.

Pull requests that touch the packaging run steps 2 only (build and smoke test, no publishing).

To publish a release:

```bash
# 1. bump `version` in pyproject.toml through a pull request, then on an up-to-date main:
git tag v0.2.0
git push origin v0.2.0
```

To build locally (the output goes to `dist/`):

```bash
.venv/bin/pip install -e ".[desktop,build]"
.venv/bin/pyinstaller --noconfirm packaging/notes.spec
QT_QPA_PLATFORM=offscreen ./dist/notes --smoke-test
```

## Project layout

```
backend/     FastAPI application
desktop/     desktop GUI: HTTP client (api_client), Qt-free UI logic (presenter), Qt window (views/),
             embedded API server for the standalone app (embedded_server)
packaging/   PyInstaller entry point and spec
tests/       pytest test suite (mirrors the package layout)
CLAUDE.md    guidance for Claude Code when working in this repo
```

## Roadmap

1. ✅ Project skeleton + first passing test
2. ✅ Pre-commit hooks that block commits on syntax errors, lint failures or failing tests
3. ✅ GitHub repository + CI pipeline (GitHub Actions) + branch protection
4. ✅ Database layer (SQLAlchemy + SQLite)
5. ✅ CRUD layer
6. ✅ `/notes` REST endpoints
7. ✅ Desktop HTTP client
8. ✅ GUI presenter (UI logic, Qt-free)
9. ✅ PySide6 main window
10. ✅ End-to-end test + docs polish
11. ✅ Release pipeline (PyInstaller builds published as GitHub Releases)
