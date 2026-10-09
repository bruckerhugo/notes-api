from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Note


def test_create_note_returns_201_and_the_created_note(client: TestClient) -> None:
    response = client.post("/notes", json={"title": "Courses", "content": "Lait, pain"})

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["title"] == "Courses"
    assert body["content"] == "Lait, pain"
    datetime.fromisoformat(body["created_at"])
    datetime.fromisoformat(body["updated_at"])


def test_create_note_content_defaults_to_empty_string(client: TestClient) -> None:
    response = client.post("/notes", json={"title": "Sans contenu"})

    assert response.status_code == 201
    assert response.json()["content"] == ""


def test_create_note_persists_it_in_database(
    client: TestClient, db_session: Session
) -> None:
    response = client.post("/notes", json={"title": "Persistée"})

    note = db_session.scalars(select(Note)).one()
    assert note.id == response.json()["id"]
    assert note.title == "Persistée"


def test_create_note_rejects_missing_title(client: TestClient) -> None:
    response = client.post("/notes", json={"content": "Pas de titre"})

    assert response.status_code == 422


def test_create_note_rejects_empty_title(client: TestClient) -> None:
    response = client.post("/notes", json={"title": ""})

    assert response.status_code == 422


def test_create_note_rejects_title_longer_than_200_chars(client: TestClient) -> None:
    response = client.post("/notes", json={"title": "x" * 201})

    assert response.status_code == 422


def _create_notes(client: TestClient, *titles: str) -> list[int]:
    return [client.post("/notes", json={"title": t}).json()["id"] for t in titles]


def test_list_notes_returns_empty_list_when_no_notes(client: TestClient) -> None:
    response = client.get("/notes")

    assert response.status_code == 200
    assert response.json() == []


def test_list_notes_returns_all_notes_ordered_by_id(client: TestClient) -> None:
    ids = _create_notes(client, "Première", "Deuxième", "Troisième")

    response = client.get("/notes")

    assert response.status_code == 200
    body = response.json()
    assert [note["id"] for note in body] == ids
    assert [note["title"] for note in body] == ["Première", "Deuxième", "Troisième"]
    assert set(body[0]) == {"id", "title", "content", "created_at", "updated_at"}


def test_list_notes_supports_skip_and_limit(client: TestClient) -> None:
    ids = _create_notes(client, "a", "b", "c", "d", "e")

    response = client.get("/notes", params={"skip": 1, "limit": 2})

    assert response.status_code == 200
    assert [note["id"] for note in response.json()] == ids[1:3]


def test_list_notes_rejects_negative_skip(client: TestClient) -> None:
    response = client.get("/notes", params={"skip": -1})

    assert response.status_code == 422


def test_list_notes_rejects_limit_out_of_range(client: TestClient) -> None:
    assert client.get("/notes", params={"limit": 0}).status_code == 422
    assert client.get("/notes", params={"limit": 101}).status_code == 422
