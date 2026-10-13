from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from backend import database
from desktop.embedded_server import EmbeddedServer


@pytest.fixture(autouse=True)
def restore_database() -> Iterator[None]:
    original = database.engine.url.render_as_string(hide_password=False)
    yield
    database.configure(original)


def test_serves_the_api_on_a_free_local_port(tmp_path: Path) -> None:
    with EmbeddedServer(tmp_path / "notes.db") as server:
        assert server.base_url.startswith("http://127.0.0.1:")
        assert not server.base_url.endswith(":0")
        response = httpx.get(f"{server.base_url}/health")

    assert response.json() == {"status": "ok"}


def test_stores_notes_in_the_given_file_across_restarts(tmp_path: Path) -> None:
    db_file = tmp_path / "data" / "notes.db"

    with EmbeddedServer(db_file) as server:
        httpx.post(f"{server.base_url}/notes", json={"title": "Persistent"})

    assert db_file.exists()
    with EmbeddedServer(db_file) as server:
        notes = httpx.get(f"{server.base_url}/notes").json()

    assert [note["title"] for note in notes] == ["Persistent"]


def test_stop_shuts_the_server_down(tmp_path: Path) -> None:
    server = EmbeddedServer(tmp_path / "notes.db")
    server.start()
    url = server.base_url

    server.stop()

    with pytest.raises(httpx.ConnectError):
        httpx.get(f"{url}/health", timeout=1)


def test_base_url_is_unavailable_before_start(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not started"):
        _ = EmbeddedServer(tmp_path / "notes.db").base_url


def test_start_fails_clearly_when_the_database_cannot_be_opened(tmp_path: Path) -> None:
    not_a_file = tmp_path / "a-directory"
    not_a_file.mkdir()

    with pytest.raises(RuntimeError, match="failed to start"):
        EmbeddedServer(not_a_file).start()


def test_stop_without_start_does_nothing(tmp_path: Path) -> None:
    EmbeddedServer(tmp_path / "notes.db").stop()
