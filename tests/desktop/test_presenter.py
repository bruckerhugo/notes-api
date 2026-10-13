from dataclasses import dataclass, field

import pytest

from desktop.api_client import ApiUnavailable, Note
from desktop.presenter import NotesPresenter
from tests.desktop.fakes import FakeNotesClient


@dataclass
class FakeView:
    """Records what the presenter asks the view to display."""

    confirm_answer: bool = True
    notes: list[Note] = field(default_factory=list)
    selected_id: int | None = None
    editor: Note | None = None
    editor_calls: int = 0
    errors: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    confirmations: list[Note] = field(default_factory=list)

    def show_notes(self, notes: list[Note], selected_id: int | None) -> None:
        self.notes = notes
        self.selected_id = selected_id

    def show_note(self, note: Note | None) -> None:
        self.editor = note
        self.editor_calls += 1

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def show_status(self, message: str) -> None:
        self.statuses.append(message)

    def confirm_delete(self, note: Note) -> bool:
        self.confirmations.append(note)
        return self.confirm_answer


def _titles(view: FakeView) -> list[str]:
    return [note.title for note in view.notes]


@pytest.fixture
def api() -> FakeNotesClient:
    return FakeNotesClient("first", "second")


@pytest.fixture
def view() -> FakeView:
    return FakeView()


@pytest.fixture
def presenter(api: FakeNotesClient, view: FakeView) -> NotesPresenter:
    presenter = NotesPresenter(api, view)
    presenter.load()
    return presenter


# --- load ---


def test_load_shows_all_notes_with_nothing_selected(
    presenter: NotesPresenter, view: FakeView
) -> None:
    assert _titles(view) == ["first", "second"]
    assert view.selected_id is None
    assert presenter.selected_id is None


def test_load_shows_an_error_when_api_is_unavailable(api: FakeNotesClient, view: FakeView) -> None:
    api.fail_with = ApiUnavailable("connection refused")

    NotesPresenter(api, view).load()

    assert view.notes == []
    assert len(view.errors) == 1
    assert "connection refused" in view.errors[0]


# --- select ---


def test_select_shows_the_note_in_the_editor(presenter: NotesPresenter, view: FakeView) -> None:
    presenter.select(2)

    assert view.editor is not None
    assert view.editor.title == "second"
    assert presenter.selected_id == 2


def test_select_a_note_deleted_elsewhere_shows_error_and_refreshes(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    del api.notes[2]

    presenter.select(2)

    assert view.errors == ["Note 2 not found"]
    assert _titles(view) == ["first"]
    assert view.editor is None
    assert presenter.selected_id is None


# --- new ---


def test_new_note_clears_editor_and_selection(presenter: NotesPresenter, view: FakeView) -> None:
    presenter.select(1)

    presenter.new_note()

    assert view.editor is None
    assert presenter.selected_id is None
    assert view.selected_id is None


# --- save ---


def test_save_without_selection_creates_a_note_and_selects_it(
    presenter: NotesPresenter, view: FakeView
) -> None:
    presenter.new_note()

    presenter.save("third", "body")

    assert _titles(view) == ["first", "second", "third"]
    assert presenter.selected_id == 3
    assert view.selected_id == 3
    assert view.editor is not None and view.editor.title == "third"
    assert view.statuses[-1] == "Note created"


def test_save_with_selection_updates_the_note(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    presenter.select(1)

    presenter.save("first renamed", "new body")

    assert api.notes[1].title == "first renamed"
    assert api.notes[1].content == "new body"
    assert _titles(view) == ["first renamed", "second"]
    assert view.selected_id == 1
    assert view.statuses[-1] == "Note saved"


def test_save_with_invalid_title_shows_error_and_keeps_editor(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    presenter.select(1)
    editor_calls = view.editor_calls

    presenter.save("   ", "body")

    assert view.errors == ["title: String should have at least 1 character"]
    assert api.notes[1].title == "first"
    assert view.editor_calls == editor_calls  # the user's input is not overwritten
    assert presenter.selected_id == 1


def test_save_a_note_deleted_elsewhere_shows_error_and_refreshes(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    presenter.select(2)
    del api.notes[2]

    presenter.save("second", "body")

    assert view.errors == ["Note 2 not found"]
    assert _titles(view) == ["first"]
    assert presenter.selected_id is None


def test_save_when_api_is_unavailable_shows_error(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    api.fail_with = ApiUnavailable("connection refused")

    presenter.save("offline", "")

    assert len(view.errors) == 1
    assert "connection refused" in view.errors[0]


# --- delete ---


def test_delete_asks_confirmation_then_removes_the_note(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    presenter.select(1)

    presenter.delete()

    assert [note.id for note in view.confirmations] == [1]
    assert 1 not in api.notes
    assert _titles(view) == ["second"]
    assert view.editor is None
    assert presenter.selected_id is None
    assert view.statuses[-1] == "Note deleted"


def test_delete_cancelled_keeps_the_note(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    view.confirm_answer = False
    presenter.select(1)

    presenter.delete()

    assert 1 in api.notes
    assert presenter.selected_id == 1


def test_delete_without_selection_does_nothing(presenter: NotesPresenter, view: FakeView) -> None:
    presenter.delete()

    assert view.confirmations == []
    assert view.errors == []


def test_delete_a_note_deleted_elsewhere_shows_error_and_refreshes(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    presenter.select(2)
    del api.notes[2]

    presenter.delete()

    assert view.errors == ["Note 2 not found"]
    assert _titles(view) == ["first"]
    assert presenter.selected_id is None


def test_select_when_api_is_unavailable_shows_error_and_keeps_selection(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    presenter.select(1)
    api.fail_with = ApiUnavailable("connection refused")

    presenter.select(2)

    assert len(view.errors) == 1
    assert "connection refused" in view.errors[0]
    assert presenter.selected_id == 1


def test_delete_when_api_is_unavailable_shows_error_and_keeps_selection(
    presenter: NotesPresenter, api: FakeNotesClient, view: FakeView
) -> None:
    presenter.select(1)
    api.fail_with = ApiUnavailable("connection refused")

    presenter.delete()

    assert len(view.errors) == 1
    assert presenter.selected_id == 1
