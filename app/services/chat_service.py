"""Chat service: conversations, messages, RAG streaming, regenerate."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.rag_agent import RagContext, rag_agent
from app.ai.providers.base import ChatMessage as ProviderMessage
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.database.session import db_session_ctx
from app.events.sse import sse_event
from app.models.chat import AIResponse, Message
from app.models.enums import (
    AIProviderEnum,
    MessageRoleEnum,
    MessageStatusEnum,
    NotificationCategoryEnum,
)
from app.models.user import User
from app.repositories.audit import UsageAnalyticsRepository
from app.repositories.chat import (
    AIResponseRepository,
    ChatSessionRepository,
    ConversationContextRepository,
    MessageRepository,
)
from app.repositories.notification import NotificationRepository
from app.repositories.repository import RepositoryRepository
from app.schemas.chat import (
    ChatConversationOut,
    ChatCreateRequest,
    ChatMessageOut,
    SendMessageRequest,
)


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sessions = ChatSessionRepository(db)
        self.messages = MessageRepository(db)
        self.ai_responses = AIResponseRepository(db)
        self.contexts = ConversationContextRepository(db)
        self.repos = RepositoryRepository(db)
        self.notifs = NotificationRepository(db)
        self.usage = UsageAnalyticsRepository(db)

    # ---- conversations ----

    async def list_conversations(
        self,
        user: User,
        *,
        repository_id: uuid.UUID | None,
        pinned_only: bool,
        saved_only: bool,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ChatConversationOut], int]:
        rows, total = await self.sessions.list_for_user(
            user.id,
            repository_id=repository_id,
            pinned_only=pinned_only,
            saved_only=saved_only,
            search=search,
            offset=offset,
            limit=limit,
        )
        return [ChatConversationOut.model_validate(r) for r in rows], total

    async def create_conversation(
        self, user: User, payload: ChatCreateRequest
    ) -> ChatConversationOut:
        repo = await self.repos.get(payload.repository_id)
        if repo is None or repo.added_by_id != user.id:
            raise NotFoundError("Repository")
        session = await self.sessions.create(
            user_id=user.id,
            repository_id=payload.repository_id,
            title=payload.title,
        )
        await self.contexts.get_or_create(session.id)
        return ChatConversationOut.model_validate(session)

    async def rename(
        self, user: User, conv_id: uuid.UUID, title: str
    ) -> ChatConversationOut:
        session = await self.sessions.get_for_user(user.id, conv_id)
        if session is None:
            raise NotFoundError("Conversation")
        session.title = title
        await self.db.flush()
        return ChatConversationOut.model_validate(session)

    async def toggle_pin(self, user: User, conv_id: uuid.UUID) -> ChatConversationOut:
        session = await self.sessions.get_for_user(user.id, conv_id)
        if session is None:
            raise NotFoundError("Conversation")
        session.is_pinned = not session.is_pinned
        await self.db.flush()
        return ChatConversationOut.model_validate(session)

    async def toggle_save(self, user: User, conv_id: uuid.UUID) -> ChatConversationOut:
        session = await self.sessions.get_for_user(user.id, conv_id)
        if session is None:
            raise NotFoundError("Conversation")
        session.is_saved = not session.is_saved
        await self.db.flush()
        return ChatConversationOut.model_validate(session)

    async def delete(self, user: User, conv_id: uuid.UUID) -> None:
        session = await self.sessions.get_for_user(user.id, conv_id)
        if session is None:
            raise NotFoundError("Conversation")
        session.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ---- messages ----

    async def list_messages(
        self, user: User, conv_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[ChatMessageOut], int]:
        session = await self.sessions.get_for_user(user.id, conv_id)
        if session is None:
            raise NotFoundError("Conversation")
        rows, total = await self.messages.list_for_session(conv_id, offset=offset, limit=limit)
        return [
            ChatMessageOut(
                id=m.id,
                conversation_id=session.id,
                role=m.role,
                content=m.content,
                status=m.status,
                created_at=m.created_at,
                references=m.references or [],
                tokens_used=m.tokens_used,
                regenerated_from=m.regenerated_from_id,
            )
            for m in rows
        ], total

    async def send_message_and_stream(
        self,
        user: User,
        conv_id: uuid.UUID,
        payload: SendMessageRequest,
    ) -> AsyncIterator[bytes]:
        session = await self.sessions.get_for_user(user.id, conv_id)
        if session is None:
            raise NotFoundError("Conversation")
        repo = await self.repos.get(session.repository_id)
        if repo is None:
            raise NotFoundError("Repository")

        user_msg = await self.messages.append(
            session_id=session.id,
            role=MessageRoleEnum.USER,
            content=payload.content,
        )
        placeholder = await self.messages.append(
            session_id=session.id,
            role=MessageRoleEnum.ASSISTANT,
            content="",
            status=MessageStatusEnum.STREAMING,
        )
        await self.sessions.touch_preview(session, payload.content)
        await self.db.commit()

        provider = payload.provider or AIProviderEnum(settings.DEFAULT_AI_PROVIDER)
        model = payload.model
        temperature = payload.temperature if payload.temperature is not None else 0.3

        ctx = await self.contexts.get_or_create(session.id)
        history_messages, _ = await self.messages.list_for_session(session.id, limit=20)
        history = [
            ProviderMessage(role=m.role.value, content=m.content)
            for m in history_messages
            if m.id not in (user_msg.id, placeholder.id) and m.content
        ]
        rag_ctx = RagContext(
            repository_id=str(session.repository_id),
            repository_full_name=repo.full_name,
            primary_language=repo.primary_language,
            active_branch=ctx.active_branch or repo.default_branch,
            history=history,
        )

        session_id = session.id
        placeholder_id = placeholder.id
        user_id = user.id
        repository_full_name = repo.full_name

        async def generator() -> AsyncIterator[bytes]:
            yield sse_event(
                "start",
                {
                    "conversationId": str(session_id),
                    "messageId": str(placeholder_id),
                    "repository": repository_full_name,
                },
            )
            started = time.perf_counter()
            content_parts: list[str] = []
            usage_prompt = usage_completion = 0
            finish_reason: str | None = None
            responding_provider = provider
            try:
                async for chunk in rag_agent.stream(
                    question=payload.content,
                    ctx=rag_ctx,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                ):
                    if chunk.delta:
                        content_parts.append(chunk.delta)
                        yield sse_event("delta", {"content": chunk.delta})
                    if chunk.done:
                        finish_reason = chunk.finish_reason
                        if chunk.usage:
                            usage_prompt = chunk.usage.prompt_tokens
                            usage_completion = chunk.usage.completion_tokens
                        if chunk.raw.get("provider"):
                            responding_provider = AIProviderEnum(chunk.raw["provider"])
                        break
            except Exception as exc:  # pragma: no cover - resilience path
                yield sse_event("error", {"message": str(exc)})
                async with db_session_ctx() as new_db:
                    row = await new_db.get(Message, placeholder_id)
                    if row:
                        row.status = MessageStatusEnum.ERROR
                        row.content = "".join(content_parts)
                return

            latency_ms = int((time.perf_counter() - started) * 1000)
            content = "".join(content_parts)
            total_tokens = usage_prompt + usage_completion
            yield sse_event(
                "usage",
                {
                    "promptTokens": usage_prompt,
                    "completionTokens": usage_completion,
                    "totalTokens": total_tokens,
                    "latencyMs": latency_ms,
                },
            )

            async with db_session_ctx() as new_db:
                row = await new_db.get(Message, placeholder_id)
                if row:
                    row.content = content
                    row.status = MessageStatusEnum.COMPLETE
                    row.tokens_used = total_tokens
                    new_db.add(
                        AIResponse(
                            message_id=row.id,
                            provider=responding_provider,
                            model=model or "auto",
                            prompt_tokens=usage_prompt,
                            completion_tokens=usage_completion,
                            total_tokens=total_tokens,
                            latency_ms=latency_ms,
                            finish_reason=finish_reason,
                            temperature=temperature,
                        )
                    )
                today = await UsageAnalyticsRepository(new_db).get_or_create_today(user_id)
                today.chat_messages_sent += 1
                today.ai_tokens_used += total_tokens

            yield sse_event(
                "done",
                {
                    "messageId": str(placeholder_id),
                    "status": MessageStatusEnum.COMPLETE.value,
                    "content": content,
                },
            )

        return generator()

    async def regenerate(
        self,
        user: User,
        conv_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> AsyncIterator[bytes]:
        session = await self.sessions.get_for_user(user.id, conv_id)
        if session is None:
            raise NotFoundError("Conversation")
        target = await self.messages.get_for_session(conv_id, message_id)
        if target is None:
            raise NotFoundError("Message")
        prior_user_content = target.content
        rows, _ = await self.messages.list_for_session(conv_id, limit=200)
        for idx, row in enumerate(rows):
            if row.id == message_id and idx > 0:
                candidate = rows[idx - 1]
                if candidate.role == MessageRoleEnum.USER:
                    prior_user_content = candidate.content
                break
        payload = SendMessageRequest(content=prior_user_content, stream=True)
        return await self.send_message_and_stream(user, conv_id, payload)
