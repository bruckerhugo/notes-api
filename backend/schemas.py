from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

# Leading/trailing whitespace is stripped before the length check,
# so a whitespace-only title is rejected.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class NoteCreate(BaseModel):
    title: Title
    content: str = ""


class NoteUpdate(BaseModel):
    """Partial update: only the fields sent by the client are changed."""

    title: Title | None = None
    content: str | None = None

    @field_validator("title", "content", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        # Defaults are not validated, so this only rejects an explicit null.
        if value is None:
            raise ValueError("may be omitted but not null")
        return value


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
