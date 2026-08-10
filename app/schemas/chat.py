"""Chat: conversations, messages, streaming payloads."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.models.enums import AIProviderEnum, MessageRoleEnum, MessageStatusEnum
from app.schemas.base import CamelBaseModel


class CodeReference(CamelBaseModel):
    file_path: str
    start_line: int
    end_line: int


class ChatMessageOut(CamelBaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRoleEnum
    content: str
    status: MessageStatusEnum
    created_at: datetime
    references: list[CodeReference] = Field(default_factory=list)
    tokens_used: int | None = None
    regenerated_from: UUID | None = None


class ChatConversationOut(CamelBaseModel):
    id: UUID
    repository_id: UUID
    title: str
    is_pinned: bool = False
    is_saved: bool = False
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: str = ""


class ChatCreateRequest(CamelBaseModel):
    repository_id: UUID
    title: str = Field(default="New conversation", max_length=255)


class ChatRenameRequest(CamelBaseModel):
    title: str = Field(min_length=1, max_length=255)


class SendMessageRequest(CamelBaseModel):
    content: str = Field(min_length=1, max_length=32_000)
    provider: AIProviderEnum | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    stream: bool = True


class StreamEvent(CamelBaseModel):
    """Envelope for SSE frames sent to the frontend during streaming."""

    event: Literal["start", "delta", "reference", "usage", "done", "error"]
    data: dict


class SuggestedPromptOut(CamelBaseModel):
    id: str
    label: str
    prompt: str
    icon: str
