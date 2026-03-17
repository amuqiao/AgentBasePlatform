import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="智能体名称")
    description: str = Field(default="", max_length=2048, description="描述")
    agent_type: str = Field(default="chat", description="类型: chat / task / workflow")
    system_prompt: str = Field(default="", description="系统提示词")
    llm_config: dict = Field(default_factory=dict, description="模型配置")
    tool_config: dict = Field(default_factory=dict, description="工具配置")


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=2048)
    system_prompt: Optional[str] = None
    llm_config: Optional[dict] = None
    tool_config: Optional[dict] = None


class PublishRequest(BaseModel):
    publish_note: str = Field(default="", max_length=512, description="版本说明")


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    creator_id: uuid.UUID
    name: str
    description: str
    agent_type: str
    status: str
    current_version: int
    system_prompt: str
    llm_config: dict = Field(default_factory=dict)
    tool_config: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_model(cls, agent) -> "AgentResponse":
        return cls(
            id=agent.id,
            tenant_id=agent.tenant_id,
            creator_id=agent.creator_id,
            name=agent.name,
            description=agent.description,
            agent_type=agent.agent_type,
            status=agent.status,
            current_version=agent.current_version,
            system_prompt=agent.system_prompt,
            llm_config=agent.model_config_json or {},
            tool_config=agent.tool_config or {},
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    agent_type: str
    status: str
    current_version: int
    created_at: datetime


class AgentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    version_number: int
    system_prompt: str
    llm_config: dict = Field(default_factory=dict)
    tool_config: dict = Field(default_factory=dict)
    publish_note: str
    created_at: datetime

    @classmethod
    def from_orm_model(cls, v) -> "AgentVersionResponse":
        return cls(
            id=v.id,
            agent_id=v.agent_id,
            version_number=v.version_number,
            system_prompt=v.system_prompt,
            llm_config=v.model_config_json or {},
            tool_config=v.tool_config or {},
            publish_note=v.publish_note,
            created_at=v.created_at,
        )
