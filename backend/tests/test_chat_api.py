"""
API test for /api/chat/stream with the LangGraph pipeline mocked out, so
CI never calls the real Gemini API (no quota burned, no network needed,
deterministic).
"""
import json

import pytest

import app.api.chat as chat_module


class _FakeGraph:
    """Stands in for agent_graph; yields the same event shapes chat.py expects."""

    async def astream_events(self, inputs, version="v2"):
        events = [
            {"event": "on_chain_start", "metadata": {"langgraph_node": "router"}},
            {"event": "on_chain_start", "metadata": {"langgraph_node": "retrieval"}},
            {
                "event": "on_chain_end",
                "metadata": {"langgraph_node": "retrieval"},
                "data": {"output": {"retrieved_docs": [{"source": "kb.md", "content": "..."}]}},
            },
            {"event": "on_chain_start", "metadata": {"langgraph_node": "synthesis"}},
            {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "synthesis"},
                "data": {"chunk": type("Chunk", (), {"content": "Hello "})()},
            },
            {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "synthesis"},
                "data": {"chunk": type("Chunk", (), {"content": "world"})()},
            },
        ]
        for event in events:
            yield event


import re


def _parse_sse(raw_text: str) -> list[dict]:
    parsed = []
    for block in re.split(r"\r?\n\r?\n", raw_text):
        if not block.strip():
            continue
        event_type, data = "message", ""
        for line in re.split(r"\r?\n", block):
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
        if data:
            parsed.append({"type": event_type, **json.loads(data)})
    return parsed


@pytest.mark.asyncio
async def test_chat_stream_persists_and_streams(client, test_session, monkeypatch):
    monkeypatch.setattr(chat_module, "agent_graph", _FakeGraph())

    async with client.stream(
        "POST", "/api/chat/stream", json={"message": "interface down"}
    ) as response:
        assert response.status_code == 200
        raw = ""
        async for chunk in response.aiter_text():
            raw += chunk

    events = _parse_sse(raw)
    event_types = [e["type"] for e in events]

    assert "meta" in event_types
    assert event_types.count("status") == 3
    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert "".join(tokens) == "Hello world"
    assert any(e["type"] == "citations" and e["sources"] == ["kb.md"] for e in events)
    assert "done" in event_types

    # Verify both turns were actually persisted to the DB.
    from sqlalchemy import select
    from app.db.models import Message

    async with test_session() as session:
        result = await session.execute(select(Message))
        messages = result.scalars().all()
    roles = sorted(m.role for m in messages)
    assert roles == ["assistant", "user"]


class _FailingGraph:
    """Simulates Gemini's 503 'high demand' error surfacing from the pipeline."""

    async def astream_events(self, inputs, version="v2"):
        class _Overloaded(Exception):
            code = 503

        raise _Overloaded("503 UNAVAILABLE raw provider dump")
        yield  # pragma: no cover  (makes this an async generator)


@pytest.mark.asyncio
async def test_provider_outage_shows_friendly_message_not_raw_error(client, monkeypatch):
    monkeypatch.setattr(chat_module, "agent_graph", _FailingGraph())

    async with client.stream(
        "POST", "/api/chat/stream", json={"message": "hello"}
    ) as response:
        raw = ""
        async for chunk in response.aiter_text():
            raw += chunk

    errors = [e for e in _parse_sse(raw) if e["type"] == "error"]
    assert len(errors) == 1
    assert "busy" in errors[0]["message"].lower()
    assert "503" not in errors[0]["message"]
    assert "UNAVAILABLE" not in errors[0]["message"]
