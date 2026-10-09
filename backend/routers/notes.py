from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.models import Note
from backend.schemas import NoteCreate, NoteRead

router = APIRouter(prefix="/notes", tags=["notes"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(data: NoteCreate, db: DbSession) -> Note:
    return crud.create_note(db, data)


@router.get("", response_model=list[NoteRead])
def list_notes(
    db: DbSession,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> Sequence[Note]:
    return crud.list_notes(db, skip=skip, limit=limit)
