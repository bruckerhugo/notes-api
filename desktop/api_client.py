"""HTTP client for the notes REST API, used by the desktop GUI."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


class NotesApiError(Exception):
    """Base class for every error raised by NotesClient."""


class ApiUnavailable(NotesApiError):
    """The API could not be reached (connection refused, timeout...)."""


class NoteNotFound(NotesApiError):
    def __init__(self, note_id: int) -> None:
        super().__init__(f"Note {note_id} not found")
        self.note_id = note_id


class ValidationError(NotesApiError):
    """The API rejected the request payload (HTTP 422)."""


@dataclass(frozen=True)
class Note:
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Note":
        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class NotesClient:
    """Wraps an injected httpx.Client and maps HTTP errors to domain exceptions."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list_notes(self, skip: int = 0, limit: int = 100) -> list[Note]:
        response = self._request("GET", "/notes", params={"skip": skip, "limit": limit})
        return [Note.from_json(item) for item in response.json()]

    def get_note(self, note_id: int) -> Note:
        return Note.from_json(self._request("GET", f"/notes/{note_id}", note_id=note_id).json())

    def create_note(self, title: str, content: str = "") -> Note:
        response = self._request("POST", "/notes", json={"title": title, "content": content})
        return Note.from_json(response.json())

    def update_note(
        self, note_id: int, *, title: str | None = None, content: str | None = None
    ) -> Note:
        # Only send the fields to change: the API does a partial update.
        changes = {
            field: value
            for field, value in (("title", title), ("content", content))
            if value is not None
        }
        response = self._request("PATCH", f"/notes/{note_id}", json=changes, note_id=note_id)
        return Note.from_json(response.json())

    def delete_note(self, note_id: int) -> None:
        self._request("DELETE", f"/notes/{note_id}", note_id=note_id)

    def _request(
        self, method: str, url: str, *, note_id: int | None = None, **kwargs: Any
    ) -> httpx.Response:
        try:
            response = self._http.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            raise ApiUnavailable(f"Notes API unavailable: {exc}") from exc

        if response.status_code == 404 and note_id is not None:
            raise NoteNotFound(note_id)
        if response.status_code == 422:
            raise ValidationError(_format_validation_errors(response))
        if response.is_error:
            raise NotesApiError(f"Unexpected response {response.status_code}: {response.text}")
        return response


def _format_validation_errors(response: httpx.Response) -> str:
    """Turn FastAPI's 422 body into a short readable message, e.g. 'title: ...'."""
    try:
        details = response.json()["detail"]
        return "; ".join(f"{err['loc'][-1]}: {err['msg']}" for err in details)
    except (ValueError, KeyError, TypeError, IndexError):
        return response.text
