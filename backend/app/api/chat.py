"""
Chat endpoints.

Streaming design: we use graph.astream_events (LangGraph/LangChain's event
stream) rather than a plain graph.invoke, and forward two kinds of events to
the frontend over SSE:
  - "status" events whenever a node starts (so the UI can show "Diagnosing...",
    "Retrieving docs...", etc. — this is what makes a multi-agent pipeline
    feel transparent instead of a black-box spinner)
  - "token" events for the synthesis node's LLM output specifically, so the
    final answer streams in like a normal chat response.
We identify "which node is this event from" via LangGraph's built-in
`langgraph_node` metadata tag, rather than tracking it ourselves.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import agent_graph
from app.agents.nodes import _extract_text
from app.core.logging_config import logger
from app.core.rate_limit import limiter
from app.core.resilience import friendly_error_message
from app.core.security import get_current_user_id
from app.db.database import get_session
from app.db.models import Conversation, Message
from app.models.schemas import ChatMessageOut, ChatRequest, ConversationOut, ConversationSummary

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _load_history(session: AsyncSession, conversation_id: str) -> list[dict]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]


async def _ensure_conversation(
    session: AsyncSession, conversation_id: str | None, user_id: str
) -> str:
    if conversation_id:
        existing = await session.get(Conversation, conversation_id)
        # Both "doesn't exist" and "exists but belongs to someone else" return
        # the same 404 — returning 403 for the second case would confirm to
        # an attacker that a given conversation_id is valid, just not theirs.
        if existing is None or existing.user_id != user_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return existing.id
    convo = Conversation(user_id=user_id)
    session.add(convo)
    await session.commit()
    await session.refresh(convo)
    return convo.id


@router.post("/stream")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    conversation_id = await _ensure_conversation(session, payload.conversation_id, user_id)
    history = await _load_history(session, conversation_id)

    # Persist the user's message immediately so it's not lost if generation fails
    session.add(Message(conversation_id=conversation_id, role="user", content=payload.message))
    await session.commit()

    async def event_generator():
        final_answer_parts: list[str] = []
        inputs = {"user_message": payload.message, "history": history}

        yield {"event": "meta", "data": json.dumps({"conversation_id": conversation_id})}

        try:
            async for event in agent_graph.astream_events(inputs, version="v2"):
                kind = event["event"]
                node_name = event.get("metadata", {}).get("langgraph_node")

                if kind == "on_chain_start" and node_name in (
                    "router", "diagnostic", "retrieval", "synthesis"
                ):
                    yield {
                        "event": "status",
                        "data": json.dumps({"node": node_name}),
                    }

                elif kind == "on_chat_model_stream" and node_name == "synthesis":
                    chunk = event["data"]["chunk"]
                    text = _extract_text(getattr(chunk, "content", ""))
                    if text:
                        final_answer_parts.append(text)
                        yield {"event": "token", "data": json.dumps({"text": text})}

                elif kind == "on_chain_end" and node_name == "retrieval":
                    docs = event["data"].get("output", {}).get("retrieved_docs", [])
                    sources = sorted({d["source"] for d in docs})
                    if sources:
                        yield {"event": "citations", "data": json.dumps({"sources": sources})}

            final_answer = "".join(final_answer_parts)
            session.add(
                Message(conversation_id=conversation_id, role="assistant", content=final_answer)
            )
            await session.commit()

            yield {"event": "done", "data": json.dumps({"conversation_id": conversation_id})}

        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent stream failed")
            yield {"event": "error", "data": json.dumps({"message": friendly_error_message(exc)})}

    return EventSourceResponse(event_generator())


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    return [
        ConversationSummary(conversation_id=c.id, created_at=c.created_at)
        for c in result.scalars().all()
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    existing = await session.get(Conversation, conversation_id)
    if existing is None or existing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    history = await _load_history(session, conversation_id)
    return ConversationOut(
        conversation_id=conversation_id,
        messages=[ChatMessageOut(**m) for m in history],
    )