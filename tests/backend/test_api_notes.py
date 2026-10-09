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
