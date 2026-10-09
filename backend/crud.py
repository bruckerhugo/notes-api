from sqlalchemy.orm import Session

from backend.models import Note
from backend.schemas import NoteCreate


def create_note(db: Session, data: NoteCreate) -> Note:
    note = Note(title=data.title, content=data.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note
