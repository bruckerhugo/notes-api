"""Wire the API client, presenter and Qt window together."""

import argparse
import faulthandler
import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

import httpx
from PySide6.QtCore import QCoreApplication, QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.api_client import NotesApiError, NotesClient
from desktop.embedded_server import EmbeddedServer
from desktop.presenter import NotesApi, NotesPresenter
from desktop.views.main_window import MainWindow

APP_NAME = "notes-api"
# A smoke test still running after this many seconds is considered hung.
SMOKE_TIMEOUT = 60.0


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

    if not args.smoke_test:
        return _run(smoke_test=False, report=report)

    report("Smoke test started")
    # Watchdog: if the smoke test hangs (e.g. on a native dialog), dump every thread's
    # stack to the log and exit, instead of blocking the build forever.
    log_file = args.smoke_log.open("a", encoding="utf-8") if args.smoke_log else None
    armed = _arm_watchdog(log_file or sys.stderr)
    if armed:
        # Also dump the Python stack on a native crash (e.g. inside Qt).
        faulthandler.enable(file=log_file or sys.stderr)
    try:
        return _run(smoke_test=True, report=report)
    except Exception:
        # Never let an exception escape a smoke test: in a windowed build it would open
        # a modal "Unhandled exception" dialog and block the run forever.
        report("Smoke test FAILED: unexpected error\n" + traceback.format_exc())
        return 1
    finally:
        if armed:
            faulthandler.cancel_dump_traceback_later()
            faulthandler.disable()
        if log_file is not None:
            log_file.close()


def _arm_watchdog(file: TextIO | None) -> bool:
    """faulthandler needs a real file descriptor (sys.stderr may be None or captured)."""
    try:
        faulthandler.dump_traceback_later(SMOKE_TIMEOUT, exit=True, file=file)
    except (AttributeError, ValueError, OSError):
        return False
    return True


def _run(*, smoke_test: bool, report: Callable[[str], None]) -> int:
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
            if not smoke_test:
                raise
            report(f"Smoke test FAILED: {exc}")
            return 1
        base_url = server.base_url

    try:
        with httpx.Client(base_url=base_url, timeout=5.0) as http:
            client = NotesClient(http)
            if smoke_test:
                # Check the API before opening the window: on failure the window would
                # show a modal error dialog, which blocks forever in a headless run.
                try:
                    count = len(client.list_notes())
                except NotesApiError as exc:
                    report(f"Smoke test FAILED: {exc}")
                    return 1
            window = create_window(client)
            window.show()
            if smoke_test:
                report(f"Smoke test OK: {base_url} answered with {count} note(s)")
                return 0
            return app.exec()
    finally:
        if server is not None:
            server.stop()
