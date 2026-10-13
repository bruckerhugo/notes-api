import pytest
from pytestqt.qtbot import QtBot

from desktop.app import DEFAULT_API_URL, api_base_url, create_window
from tests.desktop.fakes import FakeNotesClient


def test_create_window_shows_the_notes_from_the_api(qtbot: QtBot) -> None:
    window = create_window(FakeNotesClient("first", "second"))
    qtbot.addWidget(window)

    titles = [window.note_list.item(i).text() for i in range(window.note_list.count())]
    assert titles == ["first", "second"]


def test_create_window_wires_the_presenter(qtbot: QtBot) -> None:
    api = FakeNotesClient()
    window = create_window(api)
    qtbot.addWidget(window)

    window.title_edit.setText("From the window")
    window.save_button.click()

    assert [note.title for note in api.notes.values()] == ["From the window"]
    assert window.note_list.count() == 1


def test_api_base_url_defaults_to_local_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)

    assert api_base_url() == DEFAULT_API_URL == "http://127.0.0.1:8000"


def test_api_base_url_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTES_API_URL", "http://notes.example:9000")

    assert api_base_url() == "http://notes.example:9000"


def test_main_opens_the_window_and_returns_the_exit_code(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QApplication

    import desktop.app

    shown: list[str] = []

    class FakeClient:
        def __init__(self, http: object) -> None:
            pass

        def list_notes(self, skip: int = 0, limit: int = 100) -> list[object]:
            return []

    def fake_exec() -> int:
        shown.extend(w.windowTitle() for w in QApplication.topLevelWidgets() if w.isVisible())
        return 7

    real_create_window = desktop.app.create_window

    def tracked_create_window(api: object) -> object:
        # Hand the window to qtbot so it is closed and destroyed after the test;
        # a leaked live window broke the following Qt tests under coverage.
        window = real_create_window(api)
        qtbot.addWidget(window)
        return window

    monkeypatch.setattr(desktop.app, "create_window", tracked_create_window)
    monkeypatch.setattr(desktop.app, "NotesClient", FakeClient)
    monkeypatch.setattr(QApplication, "exec", staticmethod(fake_exec))

    assert desktop.app.main() == 7
    assert "Notes" in shown
