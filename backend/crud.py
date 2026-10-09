from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Note
from backend.schemas import NoteCreate


def create_note(db: Session, data: NoteCreate) -> Note:
    note = Note(title=data.title, content=data.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_notes(db: Session, skip: int = 0, limit: int = 100) -> Sequence[Note]:
    return db.scalars(select(Note).order_by(Note.id).offset(skip).limit(limit)).all()
