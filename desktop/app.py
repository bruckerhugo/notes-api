"""Wire the API client, presenter and Qt window together."""

import os
import sys

import httpx
from PySide6.QtWidgets import QApplication

from desktop.api_client import NotesClient
from desktop.presenter import NotesApi, NotesPresenter
from desktop.views.main_window import MainWindow

DEFAULT_API_URL = "http://127.0.0.1:8000"


def api_base_url() -> str:
    return os.environ.get("NOTES_API_URL", DEFAULT_API_URL)


def create_window(api: NotesApi) -> MainWindow:
    window = MainWindow()
    presenter = NotesPresenter(api, window)
    window.bind(presenter)  # the window keeps the presenter alive
    presenter.load()
    return window


def main() -> int:
    # Reuse an existing QApplication (Qt allows only one per process, e.g. under pytest-qt).
    app = QApplication.instance() or QApplication(sys.argv)
    with httpx.Client(base_url=api_base_url(), timeout=5.0) as http:
        window = create_window(NotesClient(http))
        window.show()
        return app.exec()
