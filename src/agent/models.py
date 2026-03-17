import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.database import BaseModel


class Agent(BaseModel):
    __tablename__ = "agents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    agent_type: Mapped[str] = mapped_column(String(32), default="chat")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model_config_json: Mapped[dict | None] = mapped_column("model_config", JSONB, default=dict)
    tool_config: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent", lazy="selectin", order_by="AgentVersion.version_number.desc()"
    )


class AgentVersion(BaseModel):
    __tablename__ = "agent_versions"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model_config_json: Mapped[dict | None] = mapped_column("model_config", JSONB, default=dict)
    tool_config: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    publish_note: Mapped[str] = mapped_column(Text, default="")

    agent: Mapped["Agent"] = relationship(back_populates="versions")
