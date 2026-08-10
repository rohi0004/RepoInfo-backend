"""Chat persistence: sessions (conversations), messages, AI responses."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload

from app.models.chat import AIResponse, ChatSession, ConversationContext, Message, PromptTemplate
from app.models.enums import MessageRoleEnum, MessageStatusEnum
from app.repositories.base import BaseRepository


class ChatSessionRepository(BaseRepository[ChatSession]):
    model = ChatSession

    def _visible(self, user_id: uuid.UUID) -> Select:
        return select(ChatSession).where(
            ChatSession.user_id == user_id, ChatSession.deleted_at.is_(None)
        )

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        repository_id: uuid.UUID | None = None,
        pinned_only: bool = False,
        saved_only: bool = False,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ChatSession], int]:
        stmt = self._visible(user_id)
        count_stmt = select(func.count()).select_from(ChatSession).where(
            ChatSession.user_id == user_id, ChatSession.deleted_at.is_(None)
        )
        if repository_id is not None:
            stmt = stmt.where(ChatSession.repository_id == repository_id)
            count_stmt = count_stmt.where(ChatSession.repository_id == repository_id)
        if pinned_only:
            stmt = stmt.where(ChatSession.is_pinned.is_(True))
            count_stmt = count_stmt.where(ChatSession.is_pinned.is_(True))
        if saved_only:
            stmt = stmt.where(ChatSession.is_saved.is_(True))
            count_stmt = count_stmt.where(ChatSession.is_saved.is_(True))
        if search:
            like = f"%{search.lower()}%"
            cond = or_(
                func.lower(ChatSession.title).like(like),
                func.lower(ChatSession.last_message_preview).like(like),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        stmt = stmt.order_by(ChatSession.updated_at.desc()).offset(offset).limit(limit)
        rows = list((await self.db.execute(stmt)).scalars().all())
        total = (await self.db.execute(count_stmt)).scalar_one()
        return rows, total

    async def get_for_user(self, user_id: uuid.UUID, conv_id: uuid.UUID) -> ChatSession | None:
        stmt = (
            select(ChatSession)
            .options(selectinload(ChatSession.context))
            .where(
                ChatSession.id == conv_id,
                ChatSession.user_id == user_id,
                ChatSession.deleted_at.is_(None),
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def touch_preview(self, session: ChatSession, preview: str) -> None:
        session.last_message_preview = preview[:500]
        session.last_message_at = datetime.now(timezone.utc)
        session.message_count += 1
        await self.db.flush()


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_for_session(
        self, session_id: uuid.UUID, *, offset: int = 0, limit: int = 100
    ) -> tuple[list[Message], int]:
        stmt = (
            select(Message)
            .options(selectinload(Message.ai_response))
            .where(Message.session_id == session_id, Message.deleted_at.is_(None))
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        count = (
            await self.db.execute(
                select(func.count())
                .select_from(Message)
                .where(Message.session_id == session_id, Message.deleted_at.is_(None))
            )
        ).scalar_one()
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, count

    async def append(
        self,
        *,
        session_id: uuid.UUID,
        role: MessageRoleEnum,
        content: str,
        status: MessageStatusEnum = MessageStatusEnum.COMPLETE,
        references: list[dict] | None = None,
    ) -> Message:
        msg = Message(
            session_id=session_id,
            role=role,
            content=content,
            status=status,
            references=references or [],
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def get_for_session(
        self, session_id: uuid.UUID, message_id: uuid.UUID
    ) -> Message | None:
        stmt = select(Message).where(
            Message.id == message_id,
            Message.session_id == session_id,
            Message.deleted_at.is_(None),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class AIResponseRepository(BaseRepository[AIResponse]):
    model = AIResponse


class ConversationContextRepository(BaseRepository[ConversationContext]):
    model = ConversationContext

    async def get_for_session(self, session_id: uuid.UUID) -> ConversationContext | None:
        stmt = select(ConversationContext).where(ConversationContext.session_id == session_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_or_create(self, session_id: uuid.UUID) -> ConversationContext:
        existing = await self.get_for_session(session_id)
        if existing is not None:
            return existing
        ctx = ConversationContext(session_id=session_id)
        self.db.add(ctx)
        await self.db.flush()
        return ctx


class PromptTemplateRepository(BaseRepository[PromptTemplate]):
    model = PromptTemplate

    async def list_active(self) -> list[PromptTemplate]:
        stmt = (
            select(PromptTemplate)
            .where(PromptTemplate.is_active.is_(True), PromptTemplate.deleted_at.is_(None))
            .order_by(PromptTemplate.name.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())
