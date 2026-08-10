"""AI chat: sessions (conversations), messages, provider responses, prompt templates."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import AuditedBase, Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import JSONB, pg_enum
from app.models.enums import AIProviderEnum, MessageRoleEnum, MessageStatusEnum


class ChatSession(AuditedBase):
    """Maps to the frontend's `ChatConversation`."""

    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New conversation")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_preview: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    last_message_at: Mapped[datetime | None] = mapped_column(nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    context: Mapped["ConversationContext"] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_chat_sessions_user_repo", "user_id", "repository_id"),)


class Message(AuditedBase):
    __tablename__ = "messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRoleEnum] = mapped_column(pg_enum(MessageRoleEnum, "message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[MessageStatusEnum] = mapped_column(
        pg_enum(MessageStatusEnum, "message_status"), nullable=False, default=MessageStatusEnum.COMPLETE
    )
    references: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regenerated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    ai_response: Mapped["AIResponse"] = relationship(
        back_populates="message", uselist=False, cascade="all, delete-orphan"
    )


class AIResponse(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Provider-level metadata for an assistant `Message` (1:1)."""

    __tablename__ = "ai_responses"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    provider: Mapped[AIProviderEnum] = mapped_column(pg_enum(AIProviderEnum, "ai_provider"), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    finish_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    raw_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    message: Mapped["Message"] = relationship(back_populates="ai_response")


class PromptTemplate(AuditedBase):
    __tablename__ = "prompt_templates"

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ConversationContext(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Rolling memory for a chat session: selected files/branch + summarized history,
    used to keep AI requests within the provider's context window."""

    __tablename__ = "conversation_contexts"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    active_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pinned_file_paths: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rolling_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_summarized_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["ChatSession"] = relationship(back_populates="context")
