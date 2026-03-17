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
    AgentChatRequest,
    AgentChatResponse,
    AgentCreateRequest,
    AgentResponse,
    AgentSummary,
    AgentUpdateRequest,
    AgentVersionResponse,
    PublishRequest,
)
from .service import AgentService

router = APIRouter(prefix="/api/v1/agents", tags=["智能体管理"])

# 智能体直接调用接口独立 router，避免 tags 合并导致 /docs 重复显示
chat_router = APIRouter(prefix="/api/v1/agents", tags=["智能体调用"])


@router.post("", response_model=BaseResponse[AgentResponse])
async def create_agent(
    req: AgentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AgentService(db)
    agent = await service.create_agent(
        tenant_id=current_user.tenant_id,
        creator_id=current_user.id,
        name=req.name,
        description=req.description,
        agent_type=req.agent_type,
        system_prompt=req.system_prompt,
        model_config=req.llm_config,
        tool_config=req.tool_config,
    )
    return BaseResponse(data=AgentResponse.from_orm_model(agent))


@router.get("", response_model=PagedResponse[AgentSummary])
async def list_agents(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AgentService(db)
    agents, total = await service.list_agents(
        tenant_id=current_user.tenant_id,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return PagedResponse(
        data=PagedData(
            items=[AgentSummary.from_orm_model(a) for a in agents],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
    )


@router.get("/{agent_id}", response_model=BaseResponse[AgentResponse])
async def get_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AgentService(db)
    agent = await service.get_agent(agent_id, current_user.tenant_id)
    return BaseResponse(data=AgentResponse.from_orm_model(agent))


@router.put("/{agent_id}", response_model=BaseResponse[AgentResponse])
async def update_agent(
    agent_id: uuid.UUID,
    req: AgentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AgentService(db)
    update_data = {}
    if req.name is not None:
        update_data["name"] = req.name
    if req.description is not None:
        update_data["description"] = req.description
    if req.system_prompt is not None:
        update_data["system_prompt"] = req.system_prompt
    if req.llm_config is not None:
        update_data["model_config_json"] = req.llm_config
    if req.tool_config is not None:
        update_data["tool_config"] = req.tool_config

    agent = await service.update_agent(agent_id, current_user.tenant_id, **update_data)
    return BaseResponse(data=AgentResponse.from_orm_model(agent))


@router.post("/{agent_id}/publish", response_model=BaseResponse[AgentVersionResponse])
async def publish_agent(
    agent_id: uuid.UUID,
    req: PublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AgentService(db)
    version = await service.publish_agent(agent_id, current_user.tenant_id, req.publish_note)
    return BaseResponse(data=AgentVersionResponse.from_orm_model(version))


@router.get("/{agent_id}/versions", response_model=BaseResponse[list[AgentVersionResponse]])
async def get_versions(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AgentService(db)
    versions = await service.get_versions(agent_id, current_user.tenant_id)
    return BaseResponse(data=[AgentVersionResponse.from_orm_model(v) for v in versions])


@router.delete("/{agent_id}", response_model=BaseResponse)
async def delete_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AgentService(db)
    await service.delete_agent(agent_id, current_user.tenant_id)
    return BaseResponse(message="智能体已删除")


# --------------- Agent 直接调用接口 ---------------


def _split_messages(messages: list) -> tuple[list[dict], str]:
    """将 messages 拆分为 history（前 N-1 条）和当前 user_message（最后一条）。"""
    history = [{"role": m.role, "content": m.content} for m in messages[:-1]]
    return history or None, messages[-1].content


@chat_router.post(
    "/{agent_id}/chat",
    response_model=BaseResponse[AgentChatResponse],
    summary="直接调用智能体（非流式）",
)
async def agent_chat(
    agent_id: uuid.UUID,
    req: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """无需创建会话，直接向智能体发送消息并获取回复。

    `messages` 采用 OpenAI 兼容格式，最后一条消息须为 user 角色。
    响应包含 `tool_calls` 字段，列出实际发生的工具调用记录。
    """
    from src.runtime.engine import execute_agent_chat_with_meta

    service = AgentService(db)
    agent = await service.get_agent(agent_id, current_user.tenant_id)
    history, user_message = _split_messages(req.messages)

    result = await execute_agent_chat_with_meta(
        system_prompt=agent.system_prompt,
        user_message=user_message,
        history=history,
        model_config=agent.model_config_json,
        agent_type=agent.agent_type,
        agent_name=agent.name,
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        tool_config=agent.tool_config,
    )

    from src.runtime.model_provider import normalize_llm_config

    resolved = normalize_llm_config(agent.model_config_json)
    return BaseResponse(data=AgentChatResponse(
        content=result["content"],
        agent_id=agent.id,
        agent_name=agent.name,
        agent_type=agent.agent_type,
        model=resolved["model_name"],
        tool_calls=result.get("tool_calls", []),
    ))


@chat_router.post(
    "/{agent_id}/chat/stream",
    summary="直接调用智能体（流式 SSE）",
)
async def agent_chat_stream(
    agent_id: uuid.UUID,
    req: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """无需创建会话，直接向智能体发送消息并以 SSE 流式获取回复。

    `messages` 采用 OpenAI 兼容格式，最后一条消息须为 user 角色。
    """
    from src.runtime.engine import execute_agent_chat_stream

    service = AgentService(db)
    agent = await service.get_agent(agent_id, current_user.tenant_id)
    history, user_message = _split_messages(req.messages)

    async def event_generator():
        async for chunk in execute_agent_chat_stream(
            system_prompt=agent.system_prompt,
            user_message=user_message,
            history=history,
            model_config=agent.model_config_json,
            agent_type=agent.agent_type,
            agent_name=agent.name,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            tool_config=agent.tool_config,
        ):
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
