from datetime import UTC, datetime, timedelta

import pytest
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


def test_create_note_persists_it_in_database(client: TestClient, db_session: Session) -> None:
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


def test_delete_note_returns_204_with_empty_body(client: TestClient) -> None:
    [note_id] = _create_notes(client, "À supprimer")

    response = client.delete(f"/notes/{note_id}")

    assert response.status_code == 204
    assert response.content == b""


def test_delete_note_removes_only_that_note(client: TestClient, db_session: Session) -> None:
    keep_1, removed, keep_2 = _create_notes(client, "Garder 1", "Supprimer", "Garder 2")

    client.delete(f"/notes/{removed}")

    remaining = db_session.scalars(select(Note.id).order_by(Note.id)).all()
    assert remaining == [keep_1, keep_2]


def test_delete_note_returns_404_when_note_does_not_exist(client: TestClient) -> None:
    response = client.delete("/notes/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}


def test_delete_note_twice_returns_404_the_second_time(client: TestClient) -> None:
    [note_id] = _create_notes(client, "Une seule fois")

    first = client.delete(f"/notes/{note_id}")
    second = client.delete(f"/notes/{note_id}")

    assert first.status_code == 204
    assert second.status_code == 404


def test_delete_note_rejects_non_integer_id(client: TestClient) -> None:
    response = client.delete("/notes/abc")

    assert response.status_code == 422


MAX_INT64 = 2**63 - 1


def test_delete_note_with_id_beyond_int64_returns_422(client: TestClient) -> None:
    response = client.delete(f"/notes/{MAX_INT64 + 1}")

    assert response.status_code == 422


def test_delete_note_with_max_int64_id_returns_404(client: TestClient) -> None:
    response = client.delete(f"/notes/{MAX_INT64}")

    assert response.status_code == 404


def test_list_notes_with_skip_beyond_int64_returns_422(client: TestClient) -> None:
    response = client.get("/notes", params={"skip": MAX_INT64 + 1})

    assert response.status_code == 422


def test_list_notes_with_max_int64_skip_returns_empty_list(client: TestClient) -> None:
    _create_notes(client, "a")

    response = client.get("/notes", params={"skip": MAX_INT64})

    assert response.status_code == 200
    assert response.json() == []


def test_delete_note_with_id_below_int64_returns_422(client: TestClient) -> None:
    response = client.delete(f"/notes/{-MAX_INT64 - 2}")

    assert response.status_code == 422


def test_ids_are_not_reused_after_deleting_the_last_note(client: TestClient) -> None:
    _, last_id = _create_notes(client, "A", "B")
    client.delete(f"/notes/{last_id}")

    [new_id] = _create_notes(client, "C")

    assert new_id > last_id


@pytest.mark.parametrize("blank_title", ["   ", "\t\n", " \u00a0 "])
def test_create_note_rejects_blank_title(client: TestClient, blank_title: str) -> None:
    response = client.post("/notes", json={"title": blank_title})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "title"]


def test_create_note_strips_surrounding_whitespace_from_title(client: TestClient) -> None:
    response = client.post("/notes", json={"title": "  Courses \n"})

    assert response.status_code == 201
    assert response.json()["title"] == "Courses"


def test_create_note_title_length_is_checked_after_stripping(client: TestClient) -> None:
    response = client.post("/notes", json={"title": " " + "x" * 200 + " "})

    assert response.status_code == 201
    assert response.json()["title"] == "x" * 200


@pytest.mark.parametrize("bad_id", ["1.0", "1.5", "1e0", "+1", " 1", "0x1", "1_0"])
def test_delete_note_rejects_non_canonical_integer_id(
    client: TestClient, db_session: Session, bad_id: str
) -> None:
    _create_notes(client, *[f"note {i}" for i in range(10)])

    response = client.delete(f"/notes/{bad_id}")

    assert response.status_code == 422
    assert len(db_session.scalars(select(Note)).all()) == 10


@pytest.mark.parametrize("note_id", ["0", "-1"])
def test_delete_note_accepts_zero_and_negative_ids_as_not_found(
    client: TestClient, note_id: str
) -> None:
    response = client.delete(f"/notes/{note_id}")

    assert response.status_code == 404


def test_openapi_documents_note_id_as_bounded_integer(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    [param] = paths["/notes/{note_id}"]["delete"]["parameters"]
    assert param["schema"]["type"] == "integer"
    assert param["schema"]["minimum"] == -(2**63)
    assert param["schema"]["maximum"] == MAX_INT64


def _assert_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0), f"{value!r} is not UTC-aware"
    return parsed


def test_create_note_returns_utc_aware_timestamps(client: TestClient) -> None:
    before = datetime.now(UTC)
    body = client.post("/notes", json={"title": "Horodatée"}).json()
    after = datetime.now(UTC)

    created_at = _assert_utc(body["created_at"])
    _assert_utc(body["updated_at"])
    assert before <= created_at <= after


def test_list_notes_returns_utc_aware_timestamps(client: TestClient) -> None:
    _create_notes(client, "Horodatée")

    [note] = client.get("/notes").json()

    _assert_utc(note["created_at"])
    _assert_utc(note["updated_at"])


def test_note_timestamps_read_from_database_are_utc_aware(
    client: TestClient, db_session: Session
) -> None:
    _create_notes(client, "Horodatée")

    note = db_session.scalars(select(Note)).one()

    assert note.created_at.utcoffset() == timedelta(0)
    assert note.updated_at.utcoffset() == timedelta(0)


def test_get_note_returns_the_note(client: TestClient) -> None:
    created = client.post("/notes", json={"title": "Read me", "content": "Body"}).json()

    response = client.get(f"/notes/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_note_returns_the_requested_note_among_several(client: TestClient) -> None:
    _, middle, _ = _create_notes(client, "first", "middle", "last")

    response = client.get(f"/notes/{middle}")

    assert response.status_code == 200
    assert response.json()["title"] == "middle"


def test_get_note_returns_404_when_note_does_not_exist(client: TestClient) -> None:
    _create_notes(client, "exists")

    response = client.get("/notes/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}


def test_get_note_returns_404_for_a_deleted_note(client: TestClient) -> None:
    [note_id] = _create_notes(client, "deleted")
    client.delete(f"/notes/{note_id}")

    response = client.get(f"/notes/{note_id}")

    assert response.status_code == 404


@pytest.mark.parametrize("bad_id", ["abc", "1.0", "1_0", str(MAX_INT64 + 1)])
def test_get_note_rejects_invalid_id(client: TestClient, bad_id: str) -> None:
    _create_notes(client, *[f"note {i}" for i in range(10)])

    response = client.get(f"/notes/{bad_id}")

    assert response.status_code == 422


def _create_note(client: TestClient, title: str = "Original", content: str = "Body") -> dict:
    response = client.post("/notes", json={"title": title, "content": content})
    assert response.status_code == 201
    return response.json()


def test_patch_note_updates_title_only(client: TestClient) -> None:
    note = _create_note(client)

    response = client.patch(f"/notes/{note['id']}", json={"title": "Renamed"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Renamed"
    assert body["content"] == "Body"


def test_patch_note_updates_content_only(client: TestClient) -> None:
    note = _create_note(client)

    response = client.patch(f"/notes/{note['id']}", json={"content": "New body"})

    assert response.status_code == 200
    assert response.json()["title"] == "Original"
    assert response.json()["content"] == "New body"


def test_patch_note_can_clear_content(client: TestClient) -> None:
    note = _create_note(client)

    response = client.patch(f"/notes/{note['id']}", json={"content": ""})

    assert response.status_code == 200
    assert response.json()["content"] == ""


def test_patch_note_persists_the_change(client: TestClient) -> None:
    note = _create_note(client)

    client.patch(f"/notes/{note['id']}", json={"title": "Persisted"})

    assert client.get(f"/notes/{note['id']}").json()["title"] == "Persisted"


def test_patch_note_bumps_updated_at_but_not_created_at(client: TestClient) -> None:
    note = _create_note(client)

    body = client.patch(f"/notes/{note['id']}", json={"title": "Later"}).json()

    assert body["created_at"] == note["created_at"]
    assert _assert_utc(body["updated_at"]) > _assert_utc(note["updated_at"])


def test_patch_note_with_empty_body_changes_nothing(client: TestClient) -> None:
    note = _create_note(client)

    response = client.patch(f"/notes/{note['id']}", json={})

    assert response.status_code == 200
    assert response.json() == note


def test_patch_note_strips_title_whitespace(client: TestClient) -> None:
    note = _create_note(client)

    response = client.patch(f"/notes/{note['id']}", json={"title": "  Trimmed  "})

    assert response.json()["title"] == "Trimmed"


def test_patch_note_ignores_read_only_fields(client: TestClient) -> None:
    note = _create_note(client)

    body = client.patch(
        f"/notes/{note['id']}",
        json={"id": 999, "created_at": "2000-01-01T00:00:00Z", "title": "Renamed"},
    ).json()

    assert body["id"] == note["id"]
    assert body["created_at"] == note["created_at"]


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"title": ""}, "title"),
        ({"title": "   "}, "title"),
        ({"title": "x" * 201}, "title"),
        ({"title": None}, "title"),
        ({"content": None}, "content"),
    ],
)
def test_patch_note_rejects_invalid_payload(client: TestClient, payload: dict, field: str) -> None:
    note = _create_note(client)

    response = client.patch(f"/notes/{note['id']}", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
    assert client.get(f"/notes/{note['id']}").json() == note


def test_patch_note_returns_404_when_note_does_not_exist(client: TestClient) -> None:
    _create_note(client)

    response = client.patch("/notes/999", json={"title": "Nope"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}


@pytest.mark.parametrize("bad_id", ["abc", "1.0", str(MAX_INT64 + 1)])
def test_patch_note_rejects_invalid_id(client: TestClient, bad_id: str) -> None:
    response = client.patch(f"/notes/{bad_id}", json={"title": "Nope"})

    assert response.status_code == 422
