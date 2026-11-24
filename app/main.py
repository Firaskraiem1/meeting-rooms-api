"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import connect, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the database once, when the server starts."""
    conn = connect()
    init_db(conn)
    conn.close()
    yield


app = FastAPI(title="Meeting rooms", lifespan=lifespan)


@app.get("/health")
def health():
    """Return a simple status so we can check that the API is running."""
    return {"status": "ok"}