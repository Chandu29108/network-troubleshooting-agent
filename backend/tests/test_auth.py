"""
Tests that auth is actually enforced (not just present in the code), and
that one user genuinely cannot read or continue another user's
conversation. These are the two properties Phase 4 exists to guarantee —
everything else (JWKS fetching, JWT signature verification itself) is
Clerk's own well-tested library code, not something this app needs to
re-verify.
"""
import pytest

from app.db.models import Conversation


@pytest.mark.asyncio
async def test_chat_stream_requires_auth(unauthed_client):
    response = await unauthed_client.post(
        "/api/chat/stream", json={"message": "interface down"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_requires_auth(unauthed_client):
    files = {"file": ("notes.txt", b"some content", "text/plain")}
    response = await unauthed_client.post("/api/documents/upload", files=files)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_conversations_requires_auth(unauthed_client):
    response = await unauthed_client.get("/api/chat/conversations")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_conversation(client, test_session):
    # `client` is authenticated as TEST_USER_ID (see conftest.py). `test_session`
    # is the same in-memory DB `client` is using (pytest reuses the fixture
    # instance within one test), so we can seed a conversation owned by a
    # different user directly, without needing a second authenticated client.
    async with test_session() as session:
        convo = Conversation(user_id="someone_elses_user_id")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        other_users_conversation_id = convo.id

    response = await client.get(f"/api/chat/conversations/{other_users_conversation_id}")
    assert response.status_code == 404  # not 403 — see _ensure_conversation's comment on why

    # Also can't continue it as if it were their own conversation
    response = await client.post(
        "/api/chat/stream",
        json={"conversation_id": other_users_conversation_id, "message": "hello"},
    )
    assert response.status_code == 404
