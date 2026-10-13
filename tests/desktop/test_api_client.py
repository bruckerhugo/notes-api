from collections.abc import Callable
from datetime import UTC

import httpx
import pytest
from fastapi.testclient import TestClient

from desktop.api_client import (
    ApiUnavailable,
    Note,
    NoteNotFound,
    NotesApiError,
    NotesClient,
    ValidationError,
)


@pytest.fixture
def notes(client: TestClient) -> NotesClient:
    # TestClient is an httpx.Client: NotesClient talks to the real API, without network.
    return NotesClient(client)


def _client_raising(exc: Exception) -> NotesClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return NotesClient(httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api"))


def _client_returning(status_code: int, text: str = "boom") -> NotesClient:
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code, text=text))
    return NotesClient(httpx.Client(transport=transport, base_url="http://api"))


def test_create_note_returns_a_note(notes: NotesClient) -> None:
    note = notes.create_note("Groceries", "Milk")

    assert isinstance(note, Note)
    assert isinstance(note.id, int)
    assert note.title == "Groceries"
    assert note.content == "Milk"
    assert note.created_at.tzinfo == UTC
    assert note.updated_at.tzinfo == UTC


def test_create_note_content_defaults_to_empty(notes: NotesClient) -> None:
    assert notes.create_note("No content").content == ""


def test_list_notes_returns_notes_in_order(notes: NotesClient) -> None:
    first = notes.create_note("first")
    second = notes.create_note("second")

    assert notes.list_notes() == [first, second]


def test_list_notes_forwards_pagination(notes: NotesClient) -> None:
    created = [notes.create_note(title) for title in ("a", "b", "c")]

    assert notes.list_notes(skip=1, limit=1) == [created[1]]


def test_get_note_returns_the_note(notes: NotesClient) -> None:
    created = notes.create_note("Read me")

    assert notes.get_note(created.id) == created


def test_update_note_changes_only_given_fields(notes: NotesClient) -> None:
    created = notes.create_note("Title", "Body")

    updated = notes.update_note(created.id, content="New body")

    assert updated.title == "Title"
    assert updated.content == "New body"
    assert updated.updated_at > created.updated_at


def test_update_note_can_change_title(notes: NotesClient) -> None:
    created = notes.create_note("Old")

    assert notes.update_note(created.id, title="New").title == "New"


def test_delete_note_removes_it(notes: NotesClient) -> None:
    created = notes.create_note("Bye")

    notes.delete_note(created.id)

    assert notes.list_notes() == []


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_note(999),
        lambda c: c.update_note(999, title="x"),
        lambda c: c.delete_note(999),
    ],
    ids=["get", "update", "delete"],
)
def test_missing_note_raises_note_not_found(
    notes: NotesClient, call: Callable[[NotesClient], object]
) -> None:
    with pytest.raises(NoteNotFound) as exc_info:
        call(notes)

    assert exc_info.value.note_id == 999


def test_invalid_title_raises_validation_error_with_api_message(notes: NotesClient) -> None:
    with pytest.raises(ValidationError) as exc_info:
        notes.create_note("   ")

    assert "title" in str(exc_info.value)


def test_validation_error_on_update(notes: NotesClient) -> None:
    created = notes.create_note("Valid")

    with pytest.raises(ValidationError):
        notes.update_note(created.id, title="x" * 201)


def test_connection_error_raises_api_unavailable() -> None:
    notes = _client_raising(httpx.ConnectError("connection refused"))

    with pytest.raises(ApiUnavailable):
        notes.list_notes()


def test_timeout_raises_api_unavailable() -> None:
    notes = _client_raising(httpx.ReadTimeout("too slow"))

    with pytest.raises(ApiUnavailable):
        notes.get_note(1)


def test_unexpected_status_raises_notes_api_error() -> None:
    notes = _client_returning(500)

    with pytest.raises(NotesApiError) as exc_info:
        notes.list_notes()

    assert not isinstance(exc_info.value, NoteNotFound | ValidationError | ApiUnavailable)
    assert "500" in str(exc_info.value)


def test_all_client_errors_share_a_base_class() -> None:
    for error in (NoteNotFound, ValidationError, ApiUnavailable):
        assert issubclass(error, NotesApiError)


def test_validation_error_with_non_json_body_keeps_raw_text() -> None:
    notes = _client_returning(422, text="bad input")

    with pytest.raises(ValidationError, match="bad input"):
        notes.create_note("x")
