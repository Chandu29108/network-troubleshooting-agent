"""
Pydantic schemas define the API's data contract. Keeping them separate from
DB models and LangGraph state means each layer can evolve independently —
e.g. we can add a field to the DB table without breaking the API response.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(
        default=None,
        description="Existing conversation to continue. Omit to start a new one.",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="User's message / router log / question",
    )


class Citation(BaseModel):
    source: str
    snippet: str


class ChatMessageOut(BaseModel):
    role: str
    content: str


class ConversationOut(BaseModel):
    conversation_id: str
    messages: list[ChatMessageOut]


class ConversationSummary(BaseModel):
    conversation_id: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        # SQLite stores timestamps with no timezone marker at all — reading
        # one back gives a naive datetime that's actually UTC, but doesn't
        # SAY it's UTC. If we serialize that naive value as-is, the browser
        # sees e.g. "2026-09-28T05:43:00" with no offset, and per the JS
        # Date spec, a timestamp with no offset is interpreted as LOCAL
        # time — silently shifting it by the browser's UTC offset (5:30 for
        # IST), which is exactly the "wrong time in the sidebar" bug. This
        # attaches the UTC marker explicitly so there's nothing to guess.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class DocumentUploadResponse(BaseModel):
    filename: str
    chunks_indexed: int
    message: str
