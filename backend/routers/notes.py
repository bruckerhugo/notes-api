from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.models import Note
from backend.schemas import NoteCreate, NoteRead

router = APIRouter(prefix="/notes", tags=["notes"])

DbSession = Annotated[Session, Depends(get_db)]

# SQLite stocke les entiers sur 64 bits signés : au-delà, le pilote lève OverflowError.
MAX_INT64 = 2**63 - 1
MIN_INT64 = -(2**63)
NoteId = Annotated[int, Path(ge=MIN_INT64, le=MAX_INT64)]


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(data: NoteCreate, db: DbSession) -> Note:
    return crud.create_note(db, data)


@router.get("", response_model=list[NoteRead])
def list_notes(
    db: DbSession,
    skip: Annotated[int, Query(ge=0, le=MAX_INT64)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> Sequence[Note]:
    return crud.list_notes(db, skip=skip, limit=limit)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: NoteId, db: DbSession) -> Response:
    if not crud.delete_note(db, note_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
