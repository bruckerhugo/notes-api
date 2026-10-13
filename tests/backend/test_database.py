from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend.main import app


@pytest.fixture
def restore_database() -> Iterator[None]:
    original = database.engine.url.render_as_string(hide_password=False)
    yield
    database.configure(original)


def test_configure_points_the_app_at_another_database(
    tmp_path: Path, restore_database: None
) -> None:
    db_file = tmp_path / "configured.db"

    database.configure(f"sqlite:///{db_file}")
    # `with` runs the lifespan, which must create the tables in the configured database.
    with TestClient(app) as client:
        created = client.post("/notes", json={"title": "Stored in tmp"}).json()

    assert db_file.exists()
    with TestClient(app) as client:
        assert client.get(f"/notes/{created['id']}").json()["title"] == "Stored in tmp"


def test_configure_replaces_engine_and_sessions(tmp_path: Path, restore_database: None) -> None:
    database.configure(f"sqlite:///{tmp_path / 'other.db'}")

    assert database.engine.url.database == str(tmp_path / "other.db")
    with next(database.get_db()) as session:
        assert session.get_bind() is database.engine
