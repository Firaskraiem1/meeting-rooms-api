"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import connect, init_db
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the database once at startup and close it at shutdown."""
    conn = connect()
    init_db(conn)
    app.state.conn = conn
    yield
    conn.close()


app = FastAPI(title="Meeting rooms", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    """Return a simple status so we can check that the API is running."""
    return {"status": "ok"}