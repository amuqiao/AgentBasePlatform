import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ConversationCreateRequest(BaseModel):
    agent_id: uuid.UUID = Field(..., description="智能体 ID")
    title: str = Field(default="新对话", max_length=256, description="会话标题")


class MessageSendRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8192, description="消息内容")


class ConversationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse] = Field(default_factory=list)
