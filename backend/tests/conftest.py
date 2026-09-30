"""
Shared test fixtures.

Sets required env vars before any app module is imported (Settings()
validates eagerly and would otherwise fail at import time), overrides the
DB dependency with a fresh in-memory SQLite DB per test so tests never
touch the real netagent.db or need Postgres running, and overrides Clerk
auth with a fixed test user id so most tests don't need a real Clerk
token or network access to Clerk's JWKS endpoint — auth verification
itself is covered separately in test_auth.py, which deliberately does
NOT use this override.
"""
import os

os.environ.setdefault("GOOGLE_API_KEY", "test-key-not-real")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CLERK_ISSUER", "https://test.clerk.accounts.dev")
# Forced blank, not setdefault: a real SENTRY_DSN in .env (as intended, for
# actually running the app) would otherwise leak into the test suite, since
# pydantic-settings reads .env directly. os.environ wins over .env in that
# read, so this guarantees Sentry stays off for tests regardless of what's
# configured for real runs.
os.environ["SENTRY_DSN"] = ""

import jwt
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db.database import get_session
from app.db.models import Base
from app.core.security import get_current_user_id
from app.core.rate_limit import limiter

TEST_USER_ID = "user_test_12345"

# get_current_user_id is overridden below (so tests don't need a real Clerk
# JWKS round-trip), but the rate limiter's key function reads the
# Authorization header directly and independently of that override — so
# the token still needs to exist and carry a `sub` claim for rate-limit
# tests to actually exercise per-user keying rather than falling back to
# IP. Its signature is never checked by anything in this test suite.
_TEST_TOKEN = jwt.encode({"sub": TEST_USER_ID}, key="test-signing-key", algorithm="HS256")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """
    sse-starlette stores a process-global asyncio.Event that binds to the
    first event loop that uses it. pytest-asyncio gives every test its own
    loop, so a second streaming test would crash with "bound to a different
    event loop". Resetting it per test is the standard workaround; it has
    no effect on production, which runs a single loop.
    """
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    yield


@pytest_asyncio.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_session_override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    yield session_factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_session):
    """Authenticated test client: pre-authorized as TEST_USER_ID."""
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest_asyncio.fixture
async def unauthed_client(test_session):
    """Un-authenticated test client, for verifying auth is actually enforced."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
