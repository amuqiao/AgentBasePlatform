import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.common.pagination import PaginationParams
from src.common.schemas import BaseResponse, PagedData, PagedResponse

from .schemas import (
    ConversationCreateRequest,
    ConversationResponse,
    MessageResponse,
    MessageSendRequest,
)
from .service import ConversationService

router = APIRouter(prefix="/api/v1/conversations", tags=["会话管理"])


@router.post("", response_model=BaseResponse[ConversationResponse])
async def create_conversation(
    req: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    conv = await service.create_conversation(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        agent_id=req.agent_id,
        title=req.title,
    )
    return BaseResponse(data=ConversationResponse.model_validate(conv))


@router.get("", response_model=PagedResponse[ConversationResponse])
async def list_conversations(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    convs, total = await service.list_conversations(
        user_id=current_user.id,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return PagedResponse(
        data=PagedData(
            items=[ConversationResponse.model_validate(c) for c in convs],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
    )


@router.post("/{conv_id}/messages", response_model=BaseResponse[MessageResponse])
async def send_message(
    conv_id: uuid.UUID,
    req: MessageSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    msg = await service.send_message(conv_id, current_user.id, req.content)
    return BaseResponse(data=MessageResponse.model_validate(msg))


@router.post("/{conv_id}/messages/stream")
async def send_message_stream(
    conv_id: uuid.UUID,
    req: MessageSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)

    async def event_generator():
        async for chunk in service.send_message_stream(conv_id, current_user.id, req.content):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{conv_id}/messages", response_model=PagedResponse[MessageResponse])
async def get_messages(
    conv_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    messages, total = await service.get_messages(
        conv_id, current_user.id, pagination.offset, pagination.page_size
    )
    return PagedResponse(
        data=PagedData(
            items=[MessageResponse.model_validate(m) for m in messages],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
    )


@router.delete("/{conv_id}", response_model=BaseResponse)
async def delete_conversation(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    await service.delete_conversation(conv_id, current_user.id)
    return BaseResponse(message="会话已归档")
