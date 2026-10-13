from dataclasses import dataclass, field

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from desktop.api_client import Note
from desktop.views.main_window import MainWindow
from tests.desktop.fakes import T0

NOTES = [Note(1, "first", "body 1", T0, T0), Note(2, "second", "body 2", T0, T0)]


@dataclass
class FakePresenter:
    """Records the user actions forwarded by the window."""

    calls: list[tuple[str, ...]] = field(default_factory=list)

    def select(self, note_id: int) -> None:
        self.calls.append(("select", str(note_id)))

    def new_note(self) -> None:
        self.calls.append(("new_note",))

    def save(self, title: str, content: str) -> None:
        self.calls.append(("save", title, content))

    def delete(self) -> None:
        self.calls.append(("delete",))


@pytest.fixture
def presenter() -> FakePresenter:
    return FakePresenter()


@pytest.fixture
def window(qtbot: QtBot, presenter: FakePresenter) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    window.bind(presenter)
    window.show()
    return window


def _list_titles(window: MainWindow) -> list[str]:
    return [window.note_list.item(i).text() for i in range(window.note_list.count())]


# --- NotesView: presenter -> window ---


def test_window_title(window: MainWindow) -> None:
    assert window.windowTitle() == "Notes"


def test_show_notes_lists_titles(window: MainWindow) -> None:
    window.show_notes(NOTES, selected_id=None)

    assert _list_titles(window) == ["first", "second"]
    assert window.note_list.currentRow() == -1


def test_show_notes_highlights_the_selected_note(window: MainWindow) -> None:
    window.show_notes(NOTES, selected_id=2)

    assert window.note_list.currentItem().text() == "second"


def test_show_notes_replaces_previous_list(window: MainWindow) -> None:
    window.show_notes(NOTES, selected_id=None)
    window.show_notes(NOTES[:1], selected_id=None)

    assert _list_titles(window) == ["first"]


def test_show_notes_does_not_trigger_a_selection(
    window: MainWindow, presenter: FakePresenter
) -> None:
    window.show_notes(NOTES, selected_id=1)

    assert presenter.calls == []


def test_show_note_fills_the_editor(window: MainWindow) -> None:
    window.show_note(NOTES[1])

    assert window.title_edit.text() == "second"
    assert window.content_edit.toPlainText() == "body 2"
    assert window.delete_button.isEnabled()


def test_show_note_none_clears_the_editor_for_a_new_note(window: MainWindow) -> None:
    window.show_note(NOTES[1])

    window.show_note(None)

    assert window.title_edit.text() == ""
    assert window.content_edit.toPlainText() == ""
    assert not window.delete_button.isEnabled()


def test_delete_button_is_disabled_initially(window: MainWindow) -> None:
    assert not window.delete_button.isEnabled()


def test_show_status_writes_to_the_status_bar(window: MainWindow) -> None:
    window.show_status("Note saved")

    assert window.statusBar().currentMessage() == "Note saved"


def test_show_error_opens_a_warning_dialog(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: shown.append(text))

    window.show_error("API unavailable")

    assert shown == ["API unavailable"]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [(QMessageBox.StandardButton.Yes, True), (QMessageBox.StandardButton.No, False)],
)
def test_confirm_delete_asks_the_user(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    answer: QMessageBox.StandardButton,
    expected: bool,
) -> None:
    questions: list[str] = []

    def fake_question(parent: object, title: str, text: str, *args: object) -> object:
        questions.append(text)
        return answer

    monkeypatch.setattr(QMessageBox, "question", fake_question)

    assert window.confirm_delete(NOTES[0]) is expected
    assert "first" in questions[0]


# --- user actions: window -> presenter ---


def test_clicking_a_note_selects_it(
    qtbot: QtBot, window: MainWindow, presenter: FakePresenter
) -> None:
    window.show_notes(NOTES, selected_id=None)
    item = window.note_list.item(1)

    qtbot.mouseClick(
        window.note_list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=window.note_list.visualItemRect(item).center(),
    )

    assert presenter.calls == [("select", "2")]


def test_new_button_starts_a_new_note(
    qtbot: QtBot, window: MainWindow, presenter: FakePresenter
) -> None:
    qtbot.mouseClick(window.new_button, Qt.MouseButton.LeftButton)

    assert presenter.calls == [("new_note",)]


def test_save_button_sends_the_editor_content(
    qtbot: QtBot, window: MainWindow, presenter: FakePresenter
) -> None:
    qtbot.keyClicks(window.title_edit, "Groceries")
    window.content_edit.setPlainText("Milk\nBread")

    qtbot.mouseClick(window.save_button, Qt.MouseButton.LeftButton)

    assert presenter.calls == [("save", "Groceries", "Milk\nBread")]


def test_ctrl_s_saves(qtbot: QtBot, window: MainWindow, presenter: FakePresenter) -> None:
    qtbot.keyClicks(window.title_edit, "Shortcut")

    qtbot.keyClick(window.title_edit, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)

    assert presenter.calls == [("save", "Shortcut", "")]


def test_delete_button_asks_the_presenter_to_delete(
    qtbot: QtBot, window: MainWindow, presenter: FakePresenter
) -> None:
    window.show_note(NOTES[0])

    qtbot.mouseClick(window.delete_button, Qt.MouseButton.LeftButton)

    assert presenter.calls == [("delete",)]
