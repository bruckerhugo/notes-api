import re
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.models import Note
from backend.schemas import NoteCreate, NoteRead, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"])

DbSession = Annotated[Session, Depends(get_db)]

# SQLite stores signed 64-bit integers; beyond that, the driver raises OverflowError.
MAX_INT64 = 2**63 - 1
MIN_INT64 = -(2**63)

_CANONICAL_INT = re.compile(r"-?[0-9]+")


def _require_canonical_int(value: Any) -> Any:
    # Pydantic coerces "1.0", "+1", " 1" or "1_0" to int: only accept plain digits.
    if isinstance(value, str) and not _CANONICAL_INT.fullmatch(value):
        raise ValueError("must be an integer written with digits only")
    return value


# Path() must come before BeforeValidator, otherwise OpenAPI publishes ge/le
# instead of minimum/maximum.
NoteId = Annotated[int, Path(ge=MIN_INT64, le=MAX_INT64), BeforeValidator(_require_canonical_int)]


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


def _get_note_or_404(db: Session, note_id: int) -> Note:
    note = crud.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.get("/{note_id}", response_model=NoteRead)
def get_note(note_id: NoteId, db: DbSession) -> Note:
    return _get_note_or_404(db, note_id)


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(note_id: NoteId, data: NoteUpdate, db: DbSession) -> Note:
    return crud.update_note(db, _get_note_or_404(db, note_id), data)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: NoteId, db: DbSession) -> Response:
    crud.delete_note(db, _get_note_or_404(db, note_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
