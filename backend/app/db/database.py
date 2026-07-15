"""
Async SQLAlchemy engine + session factory.

Why async: FastAPI + LangGraph both run async natively; using async SQLAlchemy
avoids blocking the event loop on DB I/O while a streaming response is open.

Why SQLite by default: zero setup, zero cost, a single file. Because we only
talk to the DB through SQLAlchemy's ORM (see db/models.py), switching to
Postgres later is just changing DATABASE_URL in .env — no code changes.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings
from app.db.models import Base

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create tables on startup if they don't exist yet."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
