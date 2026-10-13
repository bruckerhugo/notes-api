"""UI logic of the desktop app, independent of any GUI toolkit."""

from typing import Protocol

from desktop.api_client import Note, NoteNotFound, NotesApiError


class NotesApi(Protocol):
    """The subset of NotesClient used by the presenter."""

    def list_notes(self, skip: int = 0, limit: int = 100) -> list[Note]: ...

    def get_note(self, note_id: int) -> Note: ...

    def create_note(self, title: str, content: str = "") -> Note: ...

    def update_note(
        self, note_id: int, *, title: str | None = None, content: str | None = None
    ) -> Note: ...

    def delete_note(self, note_id: int) -> None: ...


class NotesView(Protocol):
    """What the presenter needs from a view (implemented by the Qt window)."""

    def show_notes(self, notes: list[Note], selected_id: int | None) -> None: ...

    def show_note(self, note: Note | None) -> None:
        """Fill the editor with a note, or clear it for a new note when None."""

    def show_error(self, message: str) -> None: ...

    def show_status(self, message: str) -> None: ...

    def confirm_delete(self, note: Note) -> bool: ...


class NotesPresenter:
    def __init__(self, api: NotesApi, view: NotesView) -> None:
        self._api = api
        self._view = view
        self._selected: Note | None = None

    @property
    def selected_id(self) -> int | None:
        return None if self._selected is None else self._selected.id

    def load(self) -> None:
        try:
            notes = self._api.list_notes()
        except NotesApiError as exc:
            self._view.show_error(str(exc))
            return
        self._view.show_notes(notes, self.selected_id)

    def select(self, note_id: int) -> None:
        try:
            self._selected = self._api.get_note(note_id)
        except NoteNotFound as exc:
            self._handle_missing_note(exc)
            return
        except NotesApiError as exc:
            self._view.show_error(str(exc))
            return
        self._view.show_note(self._selected)

    def new_note(self) -> None:
        self._selected = None
        self._view.show_note(None)
        self.load()

    def save(self, title: str, content: str) -> None:
        try:
            if self._selected is None:
                saved = self._api.create_note(title, content)
                status = "Note created"
            else:
                saved = self._api.update_note(self._selected.id, title=title, content=content)
                status = "Note saved"
        except NoteNotFound as exc:
            self._handle_missing_note(exc)
            return
        except NotesApiError as exc:
            # Keep the editor as is, so the user can fix their input.
            self._view.show_error(str(exc))
            return
        self._selected = saved
        self.load()
        self._view.show_note(saved)
        self._view.show_status(status)

    def delete(self) -> None:
        if self._selected is None or not self._view.confirm_delete(self._selected):
            return
        try:
            self._api.delete_note(self._selected.id)
        except NoteNotFound as exc:
            self._handle_missing_note(exc)
            return
        except NotesApiError as exc:
            self._view.show_error(str(exc))
            return
        self._selected = None
        self.load()
        self._view.show_note(None)
        self._view.show_status("Note deleted")

    def _handle_missing_note(self, exc: NoteNotFound) -> None:
        """The note was deleted elsewhere: tell the user and resync the list."""
        self._view.show_error(str(exc))
        self._selected = None
        self._view.show_note(None)
        self.load()
