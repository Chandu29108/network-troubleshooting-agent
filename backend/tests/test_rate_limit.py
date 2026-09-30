"""
Tests that rate limits are actually enforced. Deliberately drives real
traffic through the real endpoints (not just unit-testing the key
function) — a decorator that's wired up wrong (wrong import order, wrong
middleware registration) would only be caught by an end-to-end check
like this, not by testing _rate_limit_key in isolation.

Uses an invalid file type for the upload test so the 11th request's 400
vs 429 distinction is unambiguous and the test stays fast (no real
ingestion pipeline runs — the rate-limit check happens before the route
body, so it fires regardless of what the request would have done next).
"""
import pytest


@pytest.mark.asyncio
async def test_chat_stream_rate_limit_enforced(client, monkeypatch):
    import app.api.chat as chat_module

    class _FakeGraph:
        async def astream_events(self, inputs, version="v2"):
            yield {"event": "on_chain_start", "metadata": {"langgraph_node": "router"}}

    monkeypatch.setattr(chat_module, "agent_graph", _FakeGraph())

    statuses = []
    for _ in range(21):  # limit is 20/minute
        response = await client.post("/api/chat/stream", json={"message": "hi"})
        statuses.append(response.status_code)

    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


@pytest.mark.asyncio
async def test_upload_rate_limit_enforced(client):
    files = {"file": ("bad.exe", b"x", "application/octet-stream")}

    statuses = []
    for _ in range(11):  # limit is 10/hour
        response = await client.post("/api/documents/upload", files=files)
        statuses.append(response.status_code)

    # First 10 hit the real validation logic (rejected for file type, 400).
    assert statuses[:10] == [400] * 10
    # The 11th never reaches the route body at all — blocked by the limiter.
    assert statuses[10] == 429


@pytest.mark.asyncio
async def test_rate_limit_is_scoped_per_user(client, monkeypatch):
    """A different caller (different token `sub`) must not be affected by
    another caller's exhausted limit — proves this is per-user, not a
    single global counter. Uses a second token with a different `sub`
    directly, rather than a second HTTP client, since get_current_user_id
    is overridden at the app level for the whole test either way — the
    rate limiter's key function reads the raw header itself, independent
    of that override, which is exactly the behavior being tested here."""
    import app.api.chat as chat_module
    from tests.conftest import TEST_USER_ID
    import jwt

    class _FakeGraph:
        async def astream_events(self, inputs, version="v2"):
            yield {"event": "on_chain_start", "metadata": {"langgraph_node": "router"}}

    monkeypatch.setattr(chat_module, "agent_graph", _FakeGraph())

    for _ in range(20):
        response = await client.post("/api/chat/stream", json={"message": "hi"})
        assert response.status_code == 200
    blocked = await client.post("/api/chat/stream", json={"message": "hi"})
    assert blocked.status_code == 429

    other_token = jwt.encode({"sub": "a_completely_different_user"}, key="k", algorithm="HS256")
    still_allowed = await client.post(
        "/api/chat/stream",
        json={"message": "hi"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert still_allowed.status_code == 200
    assert TEST_USER_ID != "a_completely_different_user"  # sanity: genuinely different keys
