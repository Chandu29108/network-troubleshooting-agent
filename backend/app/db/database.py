"""
Async SQLAlchemy engine + session factory.

Why async: FastAPI + LangGraph both run async natively; using async SQLAlchemy
avoids blocking the event loop on DB I/O while a streaming response is open.

SQLite is still used for the test suite (fast, in-memory, no network), and
still works for a zero-setup local dev run. Real usage (and anything shared
between people) should point DATABASE_URL at Postgres — the ORM layer
(db/models.py) doesn't change either way. Schema changes for Postgres are
applied with Alembic (see migrations/), not create_all (below) — create_all
only ever creates missing tables, it never alters an existing one, so it's
kept as a SQLite-only convenience and is a no-op for Postgres.
"""
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base

settings = get_settings()


def _is_sqlite(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def _engine_kwargs(database_url: str) -> dict:
    """
    asyncpg needs an explicit ssl flag to talk to a hosted Postgres
    (Neon/Supabase/Railway all require TLS) — SQLAlchemy's asyncpg dialect
    doesn't understand a `?sslmode=require` query string the way psycopg
    does, so that's set here instead rather than asking for a URL format
    asyncpg can't parse. Only applied when the URL doesn't already carry
    connection args of its own.
    """
    if database_url.startswith("postgresql+asyncpg") and "ssl" not in database_url:
        return {
            "connect_args": {"ssl": True},
            # Hosted/serverless Postgres (Neon included) silently closes
            # idle connections server-side after a timeout. A production
            # traceback caught this directly: the app's own /health checks
            # kept the container "warm" every ~15s but never touch the
            # database, so the pooled DB connection sat idle, got dropped
            # by Neon, and the next real request failed with
            # `asyncpg.exceptions._base.InterfaceError: connection is
            # closed` -- SQLAlchemy's pool didn't know the connection was
            # dead until it tried to use it.
            #
            # pool_pre_ping tests each connection with a lightweight ping
            # before handing it out, transparently reconnecting if it's
            # dead, instead of surfacing the error to the request.
            # pool_recycle proactively retires connections after 5 minutes
            # so they never sit idle long enough for Neon to kill them
            # first. Both are no-ops for SQLite (not passed there).
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    return {}


def _ensure_sqlite_dir_exists(database_url: str) -> None:
    """
    SQLite will happily create the DB *file* on first connect, but it will
    not create a missing parent *directory* — it just fails with an opaque
    "unable to open database file" error instead. Docker's own Dockerfile
    creates that directory in the image, but running the app directly (e.g.
    `uvicorn app.main:app` on a dev machine, outside any container) skips
    that step entirely, so we do it here instead, once, at import time —
    covering both cases identically.
    """
    if not _is_sqlite(database_url):
        return
    # sqlite+aiosqlite:///./data/netagent.db -> path after the scheme
    raw_path = urlparse(database_url).path.lstrip("/")
    if raw_path in ("", ":memory:"):
        return
    db_path = Path(raw_path)
    if db_path.parent != Path("."):
        db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir_exists(settings.database_url)

engine = create_async_engine(
    settings.database_url, echo=False, future=True, **_engine_kwargs(settings.database_url)
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """
    SQLite-only convenience: create tables on startup if they don't exist.
    Skipped for Postgres — there, the schema is owned by Alembic
    (`alembic upgrade head`, run once before the app starts, and again
    after any future model change) so the app never silently disagrees
    with its own migration history.
    """
    if not _is_sqlite(settings.database_url):
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
