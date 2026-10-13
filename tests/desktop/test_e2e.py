"""End-to-end: the real window, presenter and NotesClient against the real API.

Only the HTTP transport (FastAPI TestClient) and the modal dialogs are replaced.
"""

from dataclasses import dataclass, field

import httpx
import pytest
from fastapi.testclient import TestClient
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Note as NoteRow
from desktop.api_client import NotesClient
from desktop.app import create_window
from desktop.views.main_window import MainWindow


@dataclass
class Dialogs:
    """Replaces the modal QMessageBox calls, which would block the tests."""

    confirm: bool = True
    errors: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


@pytest.fixture
def dialogs(monkeypatch: pytest.MonkeyPatch) -> Dialogs:
    dialogs = Dialogs()

    def warning(parent: object, title: str, text: str) -> None:
        dialogs.errors.append(text)

    def question(parent: object, title: str, text: str, *args: object) -> object:
        dialogs.questions.append(text)
        yes, no = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
        return yes if dialogs.confirm else no

    monkeypatch.setattr(QMessageBox, "warning", warning)
    monkeypatch.setattr(QMessageBox, "question", question)
    return dialogs


def _open(qtbot: QtBot, http: httpx.Client) -> MainWindow:
    window = create_window(NotesClient(http))
    qtbot.addWidget(window)
    window.show()
    return window


@pytest.fixture
def window(qtbot: QtBot, client: TestClient, dialogs: Dialogs) -> MainWindow:
    return _open(qtbot, client)


def _titles(window: MainWindow) -> list[str]:
    return [window.note_list.item(i).text() for i in range(window.note_list.count())]


def _click_note(qtbot: QtBot, window: MainWindow, title: str) -> None:
    [item] = window.note_list.findItems(title, Qt.MatchFlag.MatchExactly)
    rect = window.note_list.visualItemRect(item)
    qtbot.mouseClick(window.note_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def _type_note(qtbot: QtBot, window: MainWindow, title: str, content: str) -> None:
    window.title_edit.clear()
    qtbot.keyClicks(window.title_edit, title)
    window.content_edit.clear()
    qtbot.keyClicks(window.content_edit, content)


def _rows(db: Session) -> list[tuple[str, str]]:
    db.expire_all()  # the API commits through another session
    return [(row.title, row.content) for row in db.scalars(select(NoteRow).order_by(NoteRow.id))]


def test_create_edit_and_delete_a_note_through_the_window(
    qtbot: QtBot, window: MainWindow, db_session: Session, dialogs: Dialogs
) -> None:
    assert _titles(window) == []

    # Create
    qtbot.mouseClick(window.new_button, Qt.MouseButton.LeftButton)
    _type_note(qtbot, window, "Groceries", "Milk")
    qtbot.mouseClick(window.save_button, Qt.MouseButton.LeftButton)

    assert _rows(db_session) == [("Groceries", "Milk")]
    assert _titles(window) == ["Groceries"]
    assert window.note_list.currentItem().text() == "Groceries"
    assert window.statusBar().currentMessage() == "Note created"
    assert window.delete_button.isEnabled()

    # Edit, saved with Ctrl+S
    _type_note(qtbot, window, "Groceries list", "Milk, bread")
    qtbot.keyClick(window.content_edit, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)

    assert _rows(db_session) == [("Groceries list", "Milk, bread")]
    assert _titles(window) == ["Groceries list"]
    assert window.statusBar().currentMessage() == "Note saved"

    # Delete, after confirmation
    qtbot.mouseClick(window.delete_button, Qt.MouseButton.LeftButton)

    assert dialogs.questions == ["Delete the note “Groceries list”?"]
    assert _rows(db_session) == []
    assert _titles(window) == []
    assert window.title_edit.text() == ""
    assert not window.delete_button.isEnabled()
    assert window.statusBar().currentMessage() == "Note deleted"
    assert dialogs.errors == []


def test_existing_notes_are_listed_and_opened(
    qtbot: QtBot, client: TestClient, dialogs: Dialogs
) -> None:
    for title in ("first", "second"):
        client.post("/notes", json={"title": title, "content": f"{title} body"})

    window = _open(qtbot, client)
    _click_note(qtbot, window, "second")

    assert _titles(window) == ["first", "second"]
    assert window.title_edit.text() == "second"
    assert window.content_edit.toPlainText() == "second body"


def test_cancelling_the_deletion_keeps_the_note(
    qtbot: QtBot, client: TestClient, db_session: Session, dialogs: Dialogs
) -> None:
    client.post("/notes", json={"title": "Keep me"})
    window = _open(qtbot, client)
    dialogs.confirm = False

    _click_note(qtbot, window, "Keep me")
    qtbot.mouseClick(window.delete_button, Qt.MouseButton.LeftButton)

    assert _rows(db_session) == [("Keep me", "")]
    assert _titles(window) == ["Keep me"]
    assert window.title_edit.text() == "Keep me"


def test_invalid_title_shows_the_api_error_and_keeps_the_input(
    qtbot: QtBot, window: MainWindow, db_session: Session, dialogs: Dialogs
) -> None:
    _type_note(qtbot, window, "   ", "Unsaved text")
    qtbot.mouseClick(window.save_button, Qt.MouseButton.LeftButton)

    assert dialogs.errors == ["title: String should have at least 1 character"]
    assert _rows(db_session) == []
    assert window.content_edit.toPlainText() == "Unsaved text"


def test_note_deleted_by_another_client_is_reported_and_removed(
    qtbot: QtBot, client: TestClient, dialogs: Dialogs
) -> None:
    note_id = client.post("/notes", json={"title": "Shared"}).json()["id"]
    window = _open(qtbot, client)
    _click_note(qtbot, window, "Shared")

    client.delete(f"/notes/{note_id}")  # another user deletes it
    _type_note(qtbot, window, "Shared", "my edit")
    qtbot.mouseClick(window.save_button, Qt.MouseButton.LeftButton)

    assert dialogs.errors == [f"Note {note_id} not found"]
    assert _titles(window) == []
    assert window.title_edit.text() == ""


def test_unreachable_api_shows_an_error_at_startup(qtbot: QtBot, dialogs: Dialogs) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    http = httpx.Client(transport=httpx.MockTransport(refuse), base_url="http://api")
    window = _open(qtbot, http)

    assert _titles(window) == []
    assert len(dialogs.errors) == 1
    assert "Notes API unavailable" in dialogs.errors[0]
