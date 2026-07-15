"""
Pydantic schemas define the API's data contract. Keeping them separate from
DB models and LangGraph state means each layer can evolve independently —
e.g. we can add a field to the DB table without breaking the API response.
"""
from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(
        default=None,
        description="Existing conversation to continue. Omit to start a new one.",
    )
    message: str = Field(..., min_length=1, description="User's message / router log / question")


class Citation(BaseModel):
    source: str
    snippet: str


class ChatMessageOut(BaseModel):
    role: str
    content: str


class ConversationOut(BaseModel):
    conversation_id: str
    messages: list[ChatMessageOut]


class DocumentUploadResponse(BaseModel):
    filename: str
    chunks_indexed: int
    message: str
