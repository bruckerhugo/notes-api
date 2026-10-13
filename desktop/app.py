"""Wire the API client, presenter and Qt window together."""

import argparse
import os
import sys
from pathlib import Path

import httpx
from PySide6.QtCore import QCoreApplication, QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.api_client import NotesApiError, NotesClient
from desktop.embedded_server import EmbeddedServer
from desktop.presenter import NotesApi, NotesPresenter
from desktop.views.main_window import MainWindow

APP_NAME = "notes-api"


def api_base_url() -> str | None:
    """URL of an external API from NOTES_API_URL, or None to use the embedded server."""
    return os.environ.get("NOTES_API_URL")


def default_database_path() -> Path:
    """notes.db in the per-user data directory (e.g. ~/.local/share/notes-api)."""
    QCoreApplication.setApplicationName(APP_NAME)
    data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(data_dir) / "notes.db"


def create_window(api: NotesApi) -> MainWindow:
    window = MainWindow()
    presenter = NotesPresenter(api, window)
    window.bind(presenter)  # the window keeps the presenter alive
    presenter.load()
    return window


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="notes", description="Notes desktop app")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="start, check that the API answers, then exit (used to validate builds)",
    )
    parser.add_argument(
        "--smoke-log",
        type=Path,
        help="also write the smoke test result to this file (windowed builds have no console)",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    def report(message: str) -> None:
        print(message)
        if args.smoke_log is not None:
            with args.smoke_log.open("a", encoding="utf-8") as log:
                log.write(message + "\n")

    # Reuse an existing QApplication (Qt allows only one per process, e.g. under pytest-qt).
    app = QApplication.instance() or QApplication(sys.argv)
    QCoreApplication.setApplicationName(APP_NAME)

    server: EmbeddedServer | None = None
    base_url = api_base_url()
    if base_url is None:
        server = EmbeddedServer(default_database_path())
        try:
            server.start()
        except RuntimeError as exc:
            if not args.smoke_test:
                raise
            report(f"Smoke test FAILED: {exc}")
            return 1
        base_url = server.base_url

    try:
        with httpx.Client(base_url=base_url, timeout=5.0) as http:
            client = NotesClient(http)
            if args.smoke_test:
                # Check the API before opening the window: on failure the window would
                # show a modal error dialog, which blocks forever in a headless run.
                try:
                    count = len(client.list_notes())
                except NotesApiError as exc:
                    report(f"Smoke test FAILED: {exc}")
                    return 1
            window = create_window(client)
            window.show()
            if args.smoke_test:
                report(f"Smoke test OK: {base_url} answered with {count} note(s)")
                return 0
            return app.exec()
    finally:
        if server is not None:
            server.stop()
