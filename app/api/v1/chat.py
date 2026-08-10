"""/chat endpoints — conversations, messages, streaming."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.library import STARTERS
from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.pagination import PageParams, message_pagination_params, pagination_params
from app.events.sse import sse_response
from app.models.user import User
from app.schemas.base import MessageResponse, PaginatedResponse, Success
from app.schemas.chat import (
    ChatConversationOut,
    ChatCreateRequest,
    ChatMessageOut,
    ChatRenameRequest,
    SendMessageRequest,
    SuggestedPromptOut,
)
from app.services.chat_service import ChatService

router = APIRouter()


@router.get("/conversations", response_model=Success[PaginatedResponse[ChatConversationOut]])
async def list_conversations(
    page: PageParams = Depends(pagination_params),
    repository_id: uuid.UUID | None = Query(None, alias="repositoryId"),
    pinned_only: bool = Query(False, alias="pinnedOnly"),
    saved_only: bool = Query(False, alias="savedOnly"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await ChatService(db).list_conversations(
        user,
        repository_id=repository_id,
        pinned_only=pinned_only,
        saved_only=saved_only,
        search=page.search,
        offset=page.offset,
        limit=page.limit,
    )
    return {
        "success": True,
        "data": {
            "items": [i.model_dump(by_alias=True) for i in items],
            "page": page.page,
            "pageSize": page.page_size,
            "total": total,
            "hasNextPage": page.offset + len(items) < total,
        },
    }


@router.post(
    "/conversations",
    response_model=Success[ChatConversationOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ChatCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conv = await ChatService(db).create_conversation(user, payload)
    await db.commit()
    return {"success": True, "data": conv.model_dump(by_alias=True)}


@router.get(
    "/conversations/{conv_id}",
    response_model=Success[ChatConversationOut],
)
async def get_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChatService(db)
    session = await service.sessions.get_for_user(user.id, conv_id)
    if session is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Conversation")
    return {
        "success": True,
        "data": ChatConversationOut.model_validate(session).model_dump(by_alias=True),
    }


@router.patch(
    "/conversations/{conv_id}",
    response_model=Success[ChatConversationOut],
)
async def rename_conversation(
    conv_id: uuid.UUID,
    payload: ChatRenameRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conv = await ChatService(db).rename(user, conv_id, payload.title)
    await db.commit()
    return {"success": True, "data": conv.model_dump(by_alias=True)}


@router.post("/conversations/{conv_id}/pin", response_model=Success[ChatConversationOut])
async def toggle_pin_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conv = await ChatService(db).toggle_pin(user, conv_id)
    await db.commit()
    return {"success": True, "data": conv.model_dump(by_alias=True)}


@router.post("/conversations/{conv_id}/save", response_model=Success[ChatConversationOut])
async def toggle_save_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conv = await ChatService(db).toggle_save(user, conv_id)
    await db.commit()
    return {"success": True, "data": conv.model_dump(by_alias=True)}


@router.delete("/conversations/{conv_id}", response_model=Success[MessageResponse])
async def delete_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await ChatService(db).delete(user, conv_id)
    await db.commit()
    return {"success": True, "data": {"message": "Conversation deleted."}}


@router.get(
    "/conversations/{conv_id}/messages",
    response_model=Success[PaginatedResponse[ChatMessageOut]],
)
async def list_messages(
    conv_id: uuid.UUID,
    page: PageParams = Depends(message_pagination_params),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await ChatService(db).list_messages(
        user, conv_id, offset=page.offset, limit=page.limit
    )
    return {
        "success": True,
        "data": {
            "items": [i.model_dump(by_alias=True) for i in items],
            "page": page.page,
            "pageSize": page.page_size,
            "total": total,
            "hasNextPage": page.offset + len(items) < total,
        },
    }


@router.post("/conversations/{conv_id}/messages")
async def send_message(
    conv_id: uuid.UUID,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gen = await ChatService(db).send_message_and_stream(user, conv_id, payload)
    return sse_response(gen)


@router.post("/conversations/{conv_id}/stream")
async def stream_message(
    conv_id: uuid.UUID,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gen = await ChatService(db).send_message_and_stream(user, conv_id, payload)
    return sse_response(gen)


@router.post("/conversations/{conv_id}/messages/{message_id}/regenerate")
async def regenerate_message(
    conv_id: uuid.UUID,
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gen = await ChatService(db).regenerate(user, conv_id, message_id)
    return sse_response(gen)


@router.get("/prompt-templates", response_model=Success[list[SuggestedPromptOut]])
async def list_prompt_templates() -> dict:
    return {
        "success": True,
        "data": [
            SuggestedPromptOut(
                id=p.key,
                label=p.name,
                prompt=p.template,
                icon=p.icon,
            ).model_dump(by_alias=True)
            for p in STARTERS
        ],
    }
