import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.exceptions import ForbiddenException, NotFoundException
from src.runtime.model_provider import normalize_llm_config

from .models import Agent, AgentVersion


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_agent(
        self,
        tenant_id: uuid.UUID,
        creator_id: uuid.UUID,
        name: str,
        description: str = "",
        agent_type: str = "chat",
        system_prompt: str = "",
        model_config: dict | None = None,
        tool_config: dict | None = None,
    ) -> Agent:
        agent = Agent(
            tenant_id=tenant_id,
            creator_id=creator_id,
            name=name,
            description=description,
            agent_type=agent_type,
            system_prompt=system_prompt,
            model_config_json=normalize_llm_config(model_config),
            tool_config=tool_config or {},
        )
        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def get_agent(self, agent_id: uuid.UUID, tenant_id: uuid.UUID) -> Agent:
        result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise NotFoundException(message="智能体不存在")
        return agent

    async def list_agents(
        self, tenant_id: uuid.UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[Agent], int]:
        count_q = select(func.count()).select_from(Agent).where(Agent.tenant_id == tenant_id)
        total = (await self.db.execute(count_q)).scalar() or 0

        q = (
            select(Agent)
            .where(Agent.tenant_id == tenant_id)
            .order_by(Agent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(q)
        agents = list(result.scalars().all())
        return agents, total

    async def update_agent(
        self, agent_id: uuid.UUID, tenant_id: uuid.UUID, **kwargs
    ) -> Agent:
        agent = await self.get_agent(agent_id, tenant_id)
        if "model_config_json" in kwargs and kwargs["model_config_json"] is not None:
            kwargs["model_config_json"] = normalize_llm_config(kwargs["model_config_json"])
        for key, value in kwargs.items():
            if value is not None and hasattr(agent, key):
                setattr(agent, key, value)
        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def publish_agent(
        self, agent_id: uuid.UUID, tenant_id: uuid.UUID, publish_note: str = ""
    ) -> AgentVersion:
        agent = await self.get_agent(agent_id, tenant_id)
        new_version_number = agent.current_version + 1

        version = AgentVersion(
            agent_id=agent.id,
            version_number=new_version_number,
            system_prompt=agent.system_prompt,
            model_config_json=agent.model_config_json,
            tool_config=agent.tool_config,
            publish_note=publish_note,
        )
        self.db.add(version)

        agent.current_version = new_version_number
        agent.status = "published"
        await self.db.flush()
        await self.db.refresh(version)
        return version

    async def get_versions(
        self, agent_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[AgentVersion]:
        await self.get_agent(agent_id, tenant_id)
        result = await self.db.execute(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def delete_agent(self, agent_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        agent = await self.get_agent(agent_id, tenant_id)
        await self.db.delete(agent)
        await self.db.flush()
