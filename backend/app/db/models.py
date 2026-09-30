"""
ORM models for conversation memory.

Two tables: Conversation (one row per chat thread) and Message (one row per
turn). This is what gives the agent "conversation memory" — on every request
we load prior messages for the conversation_id and feed them back into the
LangGraph state, so the agent remembers earlier symptoms the user described.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # Clerk's `sub` claim (their user id) — a plain string, not a foreign
    # key into a local `users` table. There's no local users table because
    # nothing here needs anything about a user beyond "which id owns this
    # conversation" — Clerk is the source of truth for everything else
    # (email, name, etc.), so mirroring that into a local table would just
    # be a sync problem we don't need to have.
    user_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String)  # "user" | "assistant"
    # Text, not String: SQLite ignores the distinction, but Postgres's
    # VARCHAR without a length is unusual and Text is the honest type for
    # a field that's already capped at 20000 chars one layer up (schemas.py).
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
