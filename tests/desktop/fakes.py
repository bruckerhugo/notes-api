"""Test doubles shared by the desktop tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from desktop.api_client import Note, NoteNotFound, NotesApiError, ValidationError

T0 = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


class FakeNotesClient:
    """In-memory stand-in for NotesClient, with optional failure injection."""

    def __init__(self, *titles: str) -> None:
        self.notes: dict[int, Note] = {}
        self.next_id = 1
        self.fail_with: NotesApiError | None = None
        for title in titles:
            self.create_note(title)

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def list_notes(self, skip: int = 0, limit: int = 100) -> list[Note]:
        self._check()
        return list(self.notes.values())[skip : skip + limit]

    def get_note(self, note_id: int) -> Note:
        self._check()
        if note_id not in self.notes:
            raise NoteNotFound(note_id)
        return self.notes[note_id]

    def create_note(self, title: str, content: str = "") -> Note:
        self._check()
        if not title.strip():
            raise ValidationError("title: String should have at least 1 character")
        note = Note(self.next_id, title.strip(), content, T0, T0)
        self.notes[note.id] = note
        self.next_id += 1
        return note

    def update_note(
        self, note_id: int, *, title: str | None = None, content: str | None = None
    ) -> Note:
        note = self.get_note(note_id)
        if title is not None and not title.strip():
            raise ValidationError("title: String should have at least 1 character")
        updated = replace(
            note,
            title=note.title if title is None else title.strip(),
            content=note.content if content is None else content,
            updated_at=note.updated_at + timedelta(seconds=1),
        )
        self.notes[note_id] = updated
        return updated

    def delete_note(self, note_id: int) -> None:
        self.get_note(note_id)
        del self.notes[note_id]
