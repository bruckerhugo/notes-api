from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app

DEFAULT_DB_FILE = Path("notes.db")


@pytest.fixture(scope="session", autouse=True)
def no_default_database_file_created() -> Iterator[None]:
    """Tests must never write the default notes.db (they use in-memory or tmp databases)."""
    existed_before = DEFAULT_DB_FILE.exists()
    yield
    assert existed_before or not DEFAULT_DB_FILE.exists(), "a test created ./notes.db"


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    session_factory = sessionmaker(bind=engine)

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    # No `with`: the lifespan must not run, as it would create notes.db on disk.
    yield TestClient(app)
    app.dependency_overrides.clear()
