from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend import database
from backend.database import Base
from backend.routers import notes


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Read the module attribute: database.configure() may have replaced the engine.
    Base.metadata.create_all(database.engine)
    yield


app = FastAPI(title="Notes API", lifespan=lifespan)
app.include_router(notes.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
