import os
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///notes.db")


class Base(DeclarativeBase):
    pass


def _make_engine(database_url: str) -> Engine:
    return create_engine(database_url, connect_args={"check_same_thread": False})


engine = _make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def configure(database_url: str) -> None:
    """Point the app at another database (e.g. the desktop app's embedded server).

    Must be called before the app starts serving requests.
    """
    global engine, SessionLocal
    engine.dispose()
    engine = _make_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
