import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.runtime.model_provider import normalize_llm_config


# --------------- OpenAI 兼容响应 Schema ---------------


class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIChoice(BaseModel):
    index: int = 0
    message: OpenAIMessage
    finish_reason: str = "stop"


class OpenAIUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIChatCompletion(BaseModel):
    """非流式 chat/completions 响应（OpenAI 兼容格式 + 平台扩展字段）。"""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[OpenAIChoice]
    usage: OpenAIUsage = Field(default_factory=OpenAIUsage)
    # 平台扩展字段
    agent_id: Optional[uuid.UUID] = None
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    tool_calls: list["ToolCallRecord"] = Field(default_factory=list)


class AgentCreateRequest(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=128, description="智能体名称",
        examples=["我的AI助手"],
    )
    description: str = Field(
        default="", max_length=2048, description="描述",
        examples=["一个通用的对话智能体"],
    )
    agent_type: str = Field(
        default="chat", description="类型: chat / react / task",
        examples=["chat"],
    )
    system_prompt: str = Field(
        default="", description="系统提示词",
        examples=["你是一个有帮助的AI助手，请用简洁清晰的方式回复用户。"],
    )
    llm_config: dict = Field(
        default_factory=dict, description="模型配置",
        examples=[{"model_name": "qwen-max", "temperature": 0.7, "max_tokens": 2048}],
    )
    tool_config: dict = Field(
        default_factory=dict, description="工具配置（仅 react/task 类型使用），支持 builtin_tools / mcp_servers / skills",
        examples=[{
            "builtin_tools": ["execute_python_code", "view_text_file"],
            "mcp_servers": [{"type": "stdio", "name": "calculator", "command": "python", "args": ["-m", "scripts.mcp_test_server"]}],
            "skills": ["./skills/current-time"],
        }],
    )


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128, examples=["新名称"])
    description: Optional[str] = Field(None, max_length=2048, examples=["新描述"])
    system_prompt: Optional[str] = Field(None, examples=["你是一个专业的助手。"])
    llm_config: Optional[dict] = Field(
        None, examples=[{"model_name": "qwen-max", "temperature": 0.5}],
    )
    tool_config: Optional[dict] = Field(
        None, examples=[{"builtin_tools": ["view_text_file"]}],
    )


class PublishRequest(BaseModel):
    publish_note: str = Field(
        default="", max_length=512, description="版本说明",
        examples=["v1.0 初始版本"],
    )


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
            llm_config=normalize_llm_config(agent.model_config_json),
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
    llm_config: dict = Field(default_factory=dict)
    tool_config: dict = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_orm_model(cls, agent) -> "AgentSummary":
        return cls(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            agent_type=agent.agent_type,
            status=agent.status,
            current_version=agent.current_version,
            llm_config=normalize_llm_config(agent.model_config_json),
            tool_config=agent.tool_config or {},
            created_at=agent.created_at,
        )


# --------------- Agent 直接调用接口 ---------------


class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色: user / assistant / system", examples=["user"])
    content: str = Field(..., description="消息内容", examples=["你好，请介绍一下你自己"])


class AgentChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(
        ..., min_length=1, description="消息列表，最后一条须为 user 角色",
        examples=[[{"role": "user", "content": "你好，请介绍一下你自己"}]],
    )


class ToolCallRecord(BaseModel):
    name: str = Field(..., description="工具函数名")
    arguments: dict = Field(default_factory=dict, description="调用参数")
    result: str = Field(default="", description="工具返回结果（截断至 500 字符）")


class AgentChatResponse(BaseModel):
    content: str = Field(..., description="智能体回复内容")
    agent_id: uuid.UUID
    agent_name: str
    agent_type: str
    model: str = Field(default="", description="使用的模型名称")
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="本次请求中实际发生的工具调用记录（仅 react/task 类型）",
    )


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
            llm_config=normalize_llm_config(v.model_config_json),
            tool_config=v.tool_config or {},
            publish_note=v.publish_note,
            created_at=v.created_at,
        )
