from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Espaces de début et de fin retirés avant la vérification de la longueur :
# un titre fait uniquement d'espaces est donc refusé.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class NoteCreate(BaseModel):
    title: Title
    content: str = ""


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
