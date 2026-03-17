import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.common.pagination import PaginationParams
from src.common.schemas import BaseResponse, PagedData, PagedResponse

from .schemas import (
    AgentCreateRequest,
    AgentResponse,
    AgentSummary,
    AgentUpdateRequest,
    AgentVersionResponse,
    PublishRequest,
)
from .service import AgentService

router = APIRouter(prefix="/api/v1/agents", tags=["智能体管理"])


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
            items=[AgentSummary.model_validate(a) for a in agents],
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
